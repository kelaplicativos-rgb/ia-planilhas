from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.fetch_router import fetch_payload_router
from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
    link_parece_produto_crawler,
)

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


# ==========================================================
# SAFE
# ==========================================================
def _safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n > 0 else padrao
    except Exception:
        return padrao


# ==========================================================
# URL HELPERS
# ==========================================================
def _mesmo_dominio(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(str(url_base or "")).netloc.replace("www.", "").lower()
        d2 = urlparse(str(url or "")).netloc.replace("www.", "").lower()

        if not d1 or not d2:
            return False

        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def _normalizar_link(base_url: str, href: Any) -> str:
    try:
        href = str(href or "").strip()
        if not href:
            return ""

        href_low = href.lower()

        if href_low.startswith(("javascript:", "mailto:", "tel:", "data:")):
            return ""

        url = urljoin(base_url, href).strip()

        if not url.startswith(("http://", "https://")):
            return ""

        return url
    except Exception:
        return ""


def _eh_link_ruim(url: str) -> bool:
    try:
        u = str(url or "").strip().lower()
        if not u:
            return True

        bloqueados = [
            "#",
            "/cart",
            "/carrinho",
            "/checkout",
            "/login",
            "/entrar",
            "/conta",
            "/account",
            "/register",
            "/cadastro",
            "/favoritos",
            "/wishlist",
            "/politica",
            "/privacy",
            "/termos",
            "/terms",
            "/atendimento",
            "/contato",
            "/contact",
            "/blog",
            "/noticia",
            "/news",
            "/pagina/",
            "?page=",
            "&page=",
            "?pagina=",
            "&pagina=",
            "/categoria/",
            "/category/",
            "/collections/",
            "/search",
            "/busca",
            "whatsapp",
            "instagram",
            "facebook",
            "youtube",
        ]

        return any(item in u for item in bloqueados)
    except Exception:
        return True


def _parece_link_produto_flexivel(url: str) -> bool:
    try:
        if not url or _eh_link_ruim(url):
            return False

        low = url.lower()

        # Primeiro respeita o helper existente do projeto.
        try:
            if link_parece_produto_crawler(url):
                return True
        except Exception:
            pass

        sinais_fortes = [
            "/produto",
            "/product",
            "/prod/",
            "/item/",
            "/p/",
            "/sku/",
            "-p",
            "produto-",
            "product-",
            "/loja/",
        ]
        if any(s in low for s in sinais_fortes):
            return True

        # Heurística flexível:
        # link interno, sem âncoras ruins, com caminho mais "profundo".
        path = urlparse(low).path or ""
        partes = [p for p in path.split("/") if p.strip()]

        if len(partes) >= 2 and len(path) >= 12:
            return True

        return False
    except Exception:
        return False


# ==========================================================
# FETCH INTELIGENTE
# ==========================================================
def _fetch(url: str) -> dict[str, Any]:
    try:
        payload = fetch_payload_router(url=url, preferir_js=True) or {}
        html = str(payload.get("html") or "").strip()

        if not html:
            log_debug(f"[CRAWLER] HTML vazio: {url}", "WARNING")
            return payload

        if len(html) < 2000:
            log_debug(
                f"[CRAWLER] HTML suspeito (pequeno={len(html)}): {url}",
                "WARNING",
            )

        engine = str(payload.get("engine") or "")
        log_debug(
            f"[CRAWLER] FETCH OK | engine={engine or 'desconhecido'} | url={url}",
            "INFO",
        )
        return payload

    except Exception as e:
        log_debug(f"[CRAWLER] Erro fetch: {url} | {e}", "ERROR")
        return {}


# ==========================================================
# BAIXAR PRODUTO
# ==========================================================
def _baixar(link: str, padrao_disponivel: int) -> dict[str, Any] | None:
    payload = _fetch(link)
    html = str(payload.get("html") or "").strip()

    if not html:
        log_debug(f"[CRAWLER] Produto sem HTML: {link}", "WARNING")
        return None

    try:
        produto = extrair_produto_crawler(
            html=html,
            url=link,
            padrao_disponivel=padrao_disponivel,
            network_records=_safe_list(payload.get("network_records")),
            payload_origem=payload,
        )
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair produto: {link} | {e}", "ERROR")
        return None

    if not isinstance(produto, dict):
        log_debug(f"[CRAWLER] retorno inválido do extractor: {link}", "WARNING")
        return None

    nome = str(produto.get("Nome") or "").strip()
    if not nome:
        log_debug(f"[CRAWLER] produto sem Nome: {link}", "WARNING")
        return None

    # Blindagem mínima para link externo.
    if not str(produto.get("Link Externo") or "").strip():
        produto["Link Externo"] = link

    return produto


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def _coletar_paginas_listagem(url_inicial: str, max_paginas: int) -> list[tuple[str, str]]:
    visitadas: set[str] = set()
    fila: list[str] = [url_inicial]
    paginas: list[tuple[str, str]] = []

    while fila and len(paginas) < max_paginas:
        url = fila.pop(0)

        if not url or url in visitadas:
            continue

        visitadas.add(url)

        payload = _fetch(url)
        html = str(payload.get("html") or "").strip()

        if not html:
            continue

        paginas.append((url, html))

        try:
            novos = extrair_links_paginacao_crawler(html, url) or []
            for n in novos:
                n_norm = _normalizar_link(url, n)
                if not n_norm:
                    continue
                if not _mesmo_dominio(url_inicial, n_norm):
                    continue
                if n_norm not in visitadas and n_norm not in fila:
                    fila.append(n_norm)
        except Exception as e:
            log_debug(f"[CRAWLER] erro paginação: {url} | {e}", "WARNING")

    return paginas


# ==========================================================
# EXTRAÇÃO FORTE DE LINKS
# ==========================================================
def _extrair_links_agressivo(html: str, base_url: str) -> list[str]:
    links: list[str] = []

    # 1) tenta helper principal do projeto
    try:
        links = extrair_links_produtos_crawler(html, base_url) or []
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair_links_produtos_crawler: {e}", "WARNING")
        links = []

    # normalização inicial
    normalizados: list[str] = []
    vistos: set[str] = set()

    for item in links:
        url = _normalizar_link(base_url, item)
        if not url or url in vistos:
            continue
        if not _mesmo_dominio(base_url, url):
            continue
        vistos.add(url)
        normalizados.append(url)

    links = normalizados

    # 2) fallback agressivo real
    if len(links) < 3:
        soup = BeautifulSoup(html, "html.parser")
        candidatos: list[str] = []

        for a in soup.find_all("a"):
            href = a.get("href")
            url = _normalizar_link(base_url, href)

            if not url:
                continue

            if not _mesmo_dominio(base_url, url):
                continue

            texto_link = " ".join(a.get_text(" ", strip=True).split()).lower()
            low = url.lower()

            score = 0

            # sinais na URL
            if any(x in low for x in ["/produto", "/product", "/prod/", "/item/", "/p/", "/sku/"]):
                score += 3

            # sinais no texto do link
            if any(x in texto_link for x in ["comprar", "ver produto", "detalhes", "saiba mais"]):
                score += 2

            # sinais estruturais
            path = urlparse(low).path or ""
            partes = [p for p in path.split("/") if p.strip()]
            if len(partes) >= 2:
                score += 1

            # filtro final flexível
            if _parece_link_produto_flexivel(url):
                score += 2

            if score >= 2:
                candidatos.append(url)

        # junta e deduplica
        for item in candidatos:
            if item not in vistos:
                vistos.add(item)
                links.append(item)

    # 3) filtro final mais flexível, sem matar links bons
    links_filtrados: list[str] = []
    vistos_finais: set[str] = set()

    for link in links:
        if not link:
            continue
        if link in vistos_finais:
            continue
        if not _mesmo_dominio(base_url, link):
            continue
        if not _parece_link_produto_flexivel(link):
            continue

        vistos_finais.add(link)
        links_filtrados.append(link)

    log_debug(f"[LINKS DETECTADOS] {len(links_filtrados)}", "INFO")
    return links_filtrados


# ==========================================================
# MAIN
# ==========================================================
def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()

    max_paginas = _safe_int(max_paginas, MAX_PAGINAS)
    max_threads = _safe_int(max_threads, MAX_THREADS)
    padrao_disponivel = _safe_int(padrao_disponivel, 10)

    # Blindagem prática para evitar bloqueio agressivo.
    max_threads = min(max_threads, 5)

    progress_bar = st.progress(0)
    status = st.empty()
    detalhe = st.empty()

    progresso = 0

    def tick(valor: int, msg: str) -> None:
        nonlocal progresso
        progresso = min(100, progresso + max(0, int(valor)))
        progress_bar.progress(progresso)
        status.info(msg)

    log_debug(
        f"[CRAWLER] iniciar | url={url} | max_paginas={max_paginas} | max_threads={max_threads}",
        "INFO",
    )

    # ======================================================
    # ETAPA 1 - PAGINAÇÃO
    # ======================================================
    tick(5, "🔎 Iniciando crawler...")

    paginas = _coletar_paginas_listagem(url, max_paginas)

    tick(10, f"📄 {len(paginas)} páginas carregadas")

    # ======================================================
    # ETAPA 2 - COLETA DE LINKS
    # ======================================================
    links: list[str] = []
    total_paginas = max(len(paginas), 1)

    for i, (pagina_url, html) in enumerate(paginas, start=1):
        detalhe.info(f"🔗 Página {i}/{total_paginas}")

        try:
            novos = _extrair_links_agressivo(html, pagina_url)
            links.extend(novos)
            status.info(f"🔗 {len(links)} links coletados")
        except Exception as e:
            log_debug(f"[CRAWLER] erro ao extrair links da página {pagina_url}: {e}", "WARNING")

        progress_bar.progress(15 + int((i / total_paginas) * 25))

    # deduplicar e limitar
    dedup_links: list[str] = []
    vistos_links: set[str] = set()

    for link in links:
        if not link or link in vistos_links:
            continue
        vistos_links.add(link)
        dedup_links.append(link)

    links = dedup_links[:MAX_PRODUTOS]

    # ======================================================
    # FALLBACK DIRETO
    # ======================================================
    if not links:
        status.warning("⚠️ Tentando fallback direto...")

        payload = _fetch(url)
        html = str(payload.get("html") or "").strip()

        if html:
            try:
                links = _extrair_links_agressivo(html, url)
            except Exception as e:
                log_debug(f"[CRAWLER] erro no fallback direto: {e}", "WARNING")
                links = []

    tick(10, f"🔗 {len(links)} produtos detectados")

    # ======================================================
    # EXTRAÇÃO
    # ======================================================
    if not links:
        status.error("❌ Nenhum produto encontrado")
        log_debug("[CRAWLER] nenhum link de produto encontrado", "WARNING")
        return pd.DataFrame()

    tick(5, "📦 Extraindo produtos...")

    resultados: list[dict[str, Any]] = []
    total = len(links)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futuros = {
            executor.submit(_baixar, link, padrao_disponivel): link
            for link in links
        }

        for i, futuro in enumerate(as_completed(futuros), start=1):
            link = futuros.get(futuro, "")

            try:
                resultado = futuro.result()
                if resultado:
                    resultados.append(resultado)
            except Exception as e:
                log_debug(f"[CRAWLER] erro future produto: {link} | {e}", "ERROR")

            progresso_extra = int((i / max(total, 1)) * 50)
            progress_bar.progress(min(100, 50 + progresso_extra))

            detalhe.info(f"⚙️ Produto {i}/{total}")
            status.info(f"📦 Extraindo {i}/{total}")

    # ======================================================
    # FINAL
    # ======================================================
    if not resultados:
        status.error("❌ Nenhum produto válido")
        log_debug("[CRAWLER] nenhum produto válido após extração", "WARNING")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Link Externo" in df.columns:
        try:
            df["Link Externo"] = df["Link Externo"].astype(str).str.strip()
            df = df.drop_duplicates(subset=["Link Externo"])
        except Exception:
            pass

    progress_bar.progress(100)
    status.success(f"✅ {len(df)} produtos extraídos")
    log_debug(f"[CRAWLER] finalizado com {len(df)} produtos", "INFO")

    return df.reset_index(drop=True)
