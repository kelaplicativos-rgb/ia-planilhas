from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.scrapers.extrator_produto import (
    classificar_pagina,
    extrair_produto_html,
)
from bling_app_zero.scrapers.fetcher import baixar_html


ProgressCallback = Optional[Callable[[int, str, Dict], None]]

MAX_CATEGORIAS_PADRAO = 40
MAX_PRODUTOS_PADRAO = 200
MAX_PAGINAS_PADRAO = 260


def _callback(cb: ProgressCallback, percentual: int, etapa: str, meta: Optional[Dict] = None) -> None:
    if cb is None:
        return
    try:
        cb(
            max(0, min(100, int(percentual))),
            str(etapa or "").strip(),
            meta or {},
        )
    except Exception:
        pass


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _sem_fragmento(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path or "/", p.params, p.query, ""))


def _mesmo_dominio(url_a: str, url_b: str) -> bool:
    host_a = (urlparse(url_a).netloc or "").lower().replace("www.", "")
    host_b = (urlparse(url_b).netloc or "").lower().replace("www.", "")
    return bool(host_a and host_b and host_a == host_b)


def _eh_url_util(url: str) -> bool:
    baixa = (url or "").lower()
    if not baixa:
        return False

    bloqueios = (
        "javascript:",
        "mailto:",
        "tel:",
        "whatsapp:",
        "/cdn-cgi/",
        "/cart",
        "/carrinho",
        "/checkout",
        "/account",
        "/login",
        "/admin",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".pdf",
        ".zip",
    )
    return not any(token in baixa for token in bloqueios)


def _extrair_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: List[str] = []
    vistos: Set[str] = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        absoluto = _sem_fragmento(urljoin(base_url, href))
        if not absoluto:
            continue
        if not _eh_url_util(absoluto):
            continue
        if not _mesmo_dominio(absoluto, base_url):
            continue

        if absoluto not in vistos:
            vistos.add(absoluto)
            links.append(absoluto)

    return links


def _pontuar_link(url: str) -> Tuple[int, int]:
    baixa = url.lower()

    score_categoria = 0
    score_produto = 0

    sinais_categoria = (
        "/categoria",
        "/categorias",
        "/departamento",
        "/colecao",
        "/colecoes",
        "/collections",
        "/category",
        "/catalog",
        "?pagina=",
        "&pagina=",
        "?page=",
        "&page=",
        "/marca/",
        "/busca",
    )
    sinais_produto = (
        "/produto",
        "/product",
        "/p/",
        "/pd-",
        "/item/",
        "/sku/",
        "/shop/",
    )

    for token in sinais_categoria:
        if token in baixa:
            score_categoria += 2

    for token in sinais_produto:
        if token in baixa:
            score_produto += 2

    if baixa.count("/") >= 4:
        score_produto += 1

    return score_categoria, score_produto


def _selecionar_sementes(links: List[str], limite: int) -> List[str]:
    pontuados: List[Tuple[int, int, str]] = []

    for url in links:
        sc, sp = _pontuar_link(url)
        prioridade = max(sc, sp)
        pontuados.append((prioridade, sc - sp, url))

    pontuados.sort(key=lambda x: (-x[0], -x[1], x[2]))
    selecionados: List[str] = []
    vistos = set()

    for _, _, url in pontuados:
        if url in vistos:
            continue
        vistos.add(url)
        selecionados.append(url)
        if len(selecionados) >= limite:
            break

    return selecionados


def _produto_vazio(url: str, erro: str = "") -> Dict:
    return {
        "origem_tipo": "scraper_url",
        "origem_arquivo_ou_url": url,
        "codigo": "",
        "descricao": "",
        "descricao_curta": "",
        "nome": "",
        "preco": "",
        "preco_custo": "",
        "estoque": "",
        "gtin": "",
        "marca": "",
        "categoria": "",
        "ncm": "",
        "cest": "",
        "cfop": "",
        "unidade": "",
        "fornecedor": "",
        "cnpj_fornecedor": "",
        "imagens": "",
        "disponibilidade_site": "",
        "erro_scraper": erro,
    }


def _deduplicar_produtos(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    base = df.copy()

    for coluna in ("origem_arquivo_ou_url", "gtin", "codigo", "nome", "descricao"):
        if coluna not in base.columns:
            base[coluna] = ""

    base["_chave_url"] = base["origem_arquivo_ou_url"].astype(str).str.strip().str.lower()
    base["_chave_gtin"] = base["gtin"].astype(str).str.strip()
    base["_chave_codigo"] = base["codigo"].astype(str).str.strip().str.lower()
    base["_chave_nome"] = base["nome"].astype(str).str.strip().str.lower()

    base["_dedup"] = (
        base["_chave_gtin"].where(base["_chave_gtin"] != "", "")
        + "||"
        + base["_chave_codigo"].where(base["_chave_codigo"] != "", "")
        + "||"
        + base["_chave_nome"].where(base["_chave_nome"] != "", "")
        + "||"
        + base["_chave_url"].where(base["_chave_url"] != "", "")
    )

    base = base.drop_duplicates(subset=["_dedup"], keep="first")
    return base.drop(columns=["_chave_url", "_chave_gtin", "_chave_codigo", "_chave_nome", "_dedup"])


def extrair_produtos_de_site(
    url_inicial: str,
    progress_callback: ProgressCallback = None,
    max_categorias: int = MAX_CATEGORIAS_PADRAO,
    max_produtos: int = MAX_PRODUTOS_PADRAO,
    max_paginas: int = MAX_PAGINAS_PADRAO,
) -> pd.DataFrame:
    """
    Faz crawl do domínio do fornecedor priorizando:
    1) página inicial
    2) links fortes de categoria
    3) páginas fortes de produto
    4) paginação interna do mesmo domínio

    O callback recebe:
    (percentual, etapa, meta)
    """
    url_inicial = _normalizar_url(url_inicial)
    if not url_inicial:
        return pd.DataFrame()

    _callback(progress_callback, 2, "Preparando varredura do domínio...", {"url": url_inicial})

    inicial = baixar_html(url_inicial, timeout=25)
    if not inicial.get("ok"):
        raise RuntimeError(inicial.get("erro") or "Falha ao acessar o site inicial.")

    url_base_real = inicial.get("url") or url_inicial
    html_inicial = inicial.get("html") or ""

    _callback(progress_callback, 8, "Analisando página inicial...", {"url": url_base_real})

    links_home = _extrair_links(html_inicial, url_base_real)
    sementes = _selecionar_sementes(links_home, limite=max(20, min(max_categorias, 60)))

    fila: Deque[str] = deque([url_base_real] + sementes)
    visitadas: Set[str] = set()
    produtos_visitados: Set[str] = set()
    produtos_extraidos: List[Dict] = []
    categorias_detectadas: Set[str] = set()

    paginas_processadas = 0
    erros = 0

    while fila and paginas_processadas < max_paginas and len(produtos_extraidos) < max_produtos:
        atual = fila.popleft()
        atual = _sem_fragmento(atual)

        if not atual or atual in visitadas:
            continue
        if not _mesmo_dominio(atual, url_base_real):
            continue

        visitadas.add(atual)
        paginas_processadas += 1

        progresso_base = 10 + int((paginas_processadas / max(1, max_paginas)) * 80)
        _callback(
            progress_callback,
            min(progresso_base, 92),
            f"Varrendo página {paginas_processadas}...",
            {
                "url": atual,
                "paginas_processadas": paginas_processadas,
                "produtos_encontrados": len(produtos_extraidos),
                "categorias_detectadas": len(categorias_detectadas),
                "erros": erros,
            },
        )

        resultado = baixar_html(atual, timeout=25)
        if not resultado.get("ok"):
            erros += 1
            continue

        html = resultado.get("html") or ""
        url_final = resultado.get("url") or atual
        classificacao = classificar_pagina(html, url_final)

        if classificacao.get("is_product"):
            if url_final not in produtos_visitados:
                produto = extrair_produto_html(html, url_final)
                nome = str(produto.get("nome") or "").strip()
                preco = str(produto.get("preco") or "").strip()

                if nome:
                    produto["erro_scraper"] = ""
                    produtos_extraidos.append(produto)
                    produtos_visitados.add(url_final)

                    _callback(
                        progress_callback,
                        min(progresso_base, 95),
                        f"Produto identificado: {nome[:80]}",
                        {
                            "url": url_final,
                            "produtos_encontrados": len(produtos_extraidos),
                            "preco": preco,
                        },
                    )

        if classificacao.get("is_category"):
            categorias_detectadas.add(url_final)

        links = _extrair_links(html, url_final)

        priorizados: List[Tuple[int, str]] = []
        for link in links:
            if link in visitadas:
                continue

            sc, sp = _pontuar_link(link)
            score = (sc * 3) + (sp * 4)

            # prioriza categorias e produtos, mas mantém paginação
            if score <= 0 and ("?page=" not in link and "&page=" not in link and "?pagina=" not in link and "&pagina=" not in link):
                continue

            priorizados.append((score, link))

        priorizados.sort(key=lambda x: (-x[0], x[1]))

        adicionados_categoria = 0
        for _, link in priorizados:
            if link in visitadas or link in fila:
                continue

            if len(categorias_detectadas) < max_categorias:
                fila.append(link)
                adicionados_categoria += 1
            elif "/produto" in link.lower() or "/product" in link.lower() or "/p/" in link.lower():
                fila.append(link)

            if len(fila) >= max_paginas:
                break

    _callback(
        progress_callback,
        97,
        "Consolidando e removendo duplicidades...",
        {
            "paginas_processadas": paginas_processadas,
            "produtos_encontrados": len(produtos_extraidos),
            "categorias_detectadas": len(categorias_detectadas),
            "erros": erros,
        },
    )

    if not produtos_extraidos:
        _callback(
            progress_callback,
            100,
            "Varredura concluída sem produtos válidos.",
            {
                "paginas_processadas": paginas_processadas,
                "produtos_encontrados": 0,
                "categorias_detectadas": len(categorias_detectadas),
                "erros": erros,
            },
        )
        return pd.DataFrame()

    df = pd.DataFrame(produtos_extraidos)
    df = _deduplicar_produtos(df)

    _callback(
        progress_callback,
        100,
        "Varredura concluída.",
        {
            "paginas_processadas": paginas_processadas,
            "produtos_encontrados": len(df),
            "categorias_detectadas": len(categorias_detectadas),
            "erros": erros,
        },
    )
    return df
