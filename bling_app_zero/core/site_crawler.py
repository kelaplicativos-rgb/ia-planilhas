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
# VERSION
# ==========================================================
SITE_CRAWLER_VERSION = "V2_MODULAR_OK"


# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        return None


# ==========================================================
# SAFE
# ==========================================================
def _safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n >= 0 else padrao
    except Exception:
        return padrao


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_estoque_df(valor: Any) -> int:
    try:
        if valor is None:
            return 0

        if isinstance(valor, bool):
            return 0

        texto = _safe_str(valor)
        if not texto:
            return 0

        numero = int(float(texto.replace(",", ".")))
        if numero < 0:
            return 0

        return numero
    except Exception:
        return 0


# ==========================================================
# URL HELPERS
# ==========================================================
def _mesmo_dominio(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(_safe_str(url_base)).netloc.replace("www.", "").lower()
        d2 = urlparse(_safe_str(url)).netloc.replace("www.", "").lower()

        if not d1 or not d2:
            return False

        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def _normalizar_link(base_url: str, href: Any) -> str:
    try:
        href = _safe_str(href)
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
        u = _safe_str(url).lower()
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
        html = _safe_str(payload.get("html"))

        if not html:
            log_debug(f"[CRAWLER] HTML vazio: {url}", "WARNING")
            return payload

        if len(html) < 2000:
            log_debug(
                f"[CRAWLER] HTML suspeito (pequeno={len(html)}): {url}",
                "WARNING",
            )

        engine = _safe_str(payload.get("engine")) or "desconhecido"
        log_debug(
            f"[CRAWLER] FETCH OK | engine={engine} | url={url}",
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
    html = _safe_str(payload.get("html"))

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

    nome = _safe_str(produto.get("Nome"))
    if not nome:
        log_debug(f"[CRAWLER] produto sem Nome: {link}", "WARNING")
        return None

    if not _safe_str(produto.get("Link Externo")):
        produto["Link Externo"] = link

    produto["Estoque"] = _normalizar_estoque_df(produto.get("Estoque", 0))

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
        html = _safe_str(payload.get("html"))

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

    try:
        links = extrair_links_produtos_crawler(html, base_url) or []
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair_links_produtos_crawler: {e}", "WARNING")
        links = []

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

            if any(x in low for x in ["/produto", "/product", "/prod/", "/item/", "/p/", "/sku/"]):
                score += 3

            if any(x in texto_link for x in ["comprar", "ver produto", "detalhes", "saiba mais"]):
                score += 2

            path = urlparse(low).path or ""
            partes = [p for p in path.split("/") if p.strip()]
            if len(partes) >= 2:
                score += 1

            if _parece_link_produto_flexivel(url):
                score += 2

            if score >= 2:
                candidatos.append(url)

        for item in candidatos:
            if item not in vistos:
                vistos.add(item)
                links.append(item)

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
# EXECUÇÃO ESTÁVEL
# ==========================================================
def _executar_extracao_sequencial(
    links: list[str],
    padrao_disponivel: int,
    progress_bar,
    status,
    detalhe,
) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    total = len(links)

    for i, link in enumerate(links, start=1):
        try:
            resultado = _baixar(link, padrao_disponivel)
            if resultado:
                resultados.append(resultado)
        except Exception as e:
            log_debug(f"[CRAWLER] erro produto sequencial: {link} | {e}", "ERROR")

        progresso_extra = int((i / max(total, 1)) * 50)
        progress_bar.progress(min(100, 50 + progresso_extra))
        detalhe.info(f"⚙️ Produto {i}/{total}")
        status.info(f"📦 Extraindo {i}/{total}")

    return resultados


def _executar_extracao_threads(
    links: list[str],
    padrao_disponivel: int,
    max_threads: int,
    progress_bar,
    status,
    detalhe,
) -> list[dict[str, Any]]:
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

    return resultados


# ==========================================================
# MAIN
# ==========================================================
def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 0,
) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()

    max_paginas = _safe_int(max_paginas, MAX_PAGINAS)
    max_threads = _safe_int(max_threads, MAX_THREADS)

    # regra correta do projeto: nunca depender de 10 fake
    padrao_disponivel = _safe_int(padrao_disponivel, 0)

    # blindagem de estabilidade para evitar ScriptRunContext em produção
    max_threads = 1

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
        f"[CRAWLER] iniciar | version={SITE_CRAWLER_VERSION} | url={url} | max_paginas={max_paginas} | max_threads={max_threads}",
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
        html = _safe_str(payload.get("html"))

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

    if max_threads <= 1:
        resultados = _executar_extracao_sequencial(
            links=links,
            padrao_disponivel=padrao_disponivel,
            progress_bar=progress_bar,
            status=status,
            detalhe=detalhe,
        )
    else:
        resultados = _executar_extracao_threads(
            links=links,
            padrao_disponivel=padrao_disponivel,
            max_threads=max_threads,
            progress_bar=progress_bar,
            status=status,
            detalhe=detalhe,
        )

    # ======================================================
    # FINAL
    # ======================================================
    if not resultados:
        status.error("❌ Nenhum produto válido")
        log_debug("[CRAWLER] nenhum produto válido após extração", "WARNING")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Estoque" in df.columns:
        try:
            df["Estoque"] = df["Estoque"].apply(_normalizar_estoque_df)
        except Exception:
            df["Estoque"] = 0

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
