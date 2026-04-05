from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Set
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

from .extrator_produto import classificar_pagina, extrair_produto_html
from .fetcher import baixar_html


COLUNAS_PADRAO = [
    "origem_tipo",
    "origem_arquivo_ou_url",
    "codigo",
    "descricao",
    "descricao_curta",
    "nome",
    "preco",
    "preco_custo",
    "estoque",
    "gtin",
    "marca",
    "categoria",
    "ncm",
    "cest",
    "cfop",
    "unidade",
    "fornecedor",
    "cnpj_fornecedor",
    "imagens",
    "disponibilidade_site",
    "erro_scraper",
]

PRODUCT_HINTS = (
    "/produto",
    "/product",
    "/p/",
    "/pd-",
    "/shop/",
    "/item/",
    "/sku/",
)

CATEGORY_HINTS = (
    "/categoria",
    "/categorias",
    "/category",
    "/departamento",
    "/colecao",
    "/colecoes",
    "/collections",
    "/catalog",
    "/loja/",
)

PAGINATION_TOKENS = (
    "page=",
    "pagina=",
    "p=",
    "/page/",
    "?pg=",
    "?page=",
)


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    path = parsed.path or "/"
    normalized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )
    return normalized.rstrip("/") if path != "/" else normalized


def _mesmo_dominio(url_base: str, url_destino: str) -> bool:
    base_host = (urlparse(url_base).netloc or "").lower().replace("www.", "")
    dest_host = (urlparse(url_destino).netloc or "").lower().replace("www.", "")
    return bool(base_host) and base_host == dest_host


def _coletar_links(html: str, url_base: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: List[str] = []
    vistos: Set[str] = set()

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absoluto = _normalizar_url(urljoin(url_base, href))
        if not absoluto:
            continue
        if not _mesmo_dominio(url_base, absoluto):
            continue
        if absoluto in vistos:
            continue

        vistos.add(absoluto)
        links.append(absoluto)

    return links


def _eh_link_produto(url: str) -> bool:
    url_baixa = (url or "").lower()
    return any(token in url_baixa for token in PRODUCT_HINTS)


def _eh_link_categoria(url: str) -> bool:
    url_baixa = (url or "").lower()
    return any(token in url_baixa for token in CATEGORY_HINTS)


def _eh_link_paginacao(url: str) -> bool:
    url_baixa = (url or "").lower()
    return any(token in url_baixa for token in PAGINATION_TOKENS)


def _garantir_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for coluna in COLUNAS_PADRAO:
        if coluna not in df.columns:
            df[coluna] = ""
    return df[COLUNAS_PADRAO]


def _linha_erro(url: str, erro: str) -> Dict[str, str]:
    return {
        "origem_tipo": "scraper_site",
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


def _deduplicar_produtos(produtos: List[Dict]) -> List[Dict]:
    vistos: Set[str] = set()
    saida: List[Dict] = []

    for item in produtos:
        chave = "|".join(
            [
                str(item.get("origem_arquivo_ou_url", "")).strip().lower(),
                str(item.get("codigo", "")).strip().lower(),
                str(item.get("nome", "")).strip().lower(),
                str(item.get("gtin", "")).strip(),
            ]
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(item)

    return saida


def extrair_produtos_de_site(
    url_inicial: str,
    limite_paginas: int = 60,
    limite_produtos: int = 200,
) -> pd.DataFrame:
    url_inicial = _normalizar_url(url_inicial)
    if not url_inicial:
        return _garantir_colunas(pd.DataFrame([_linha_erro("", "URL inválida.")]))

    fila_paginas = deque([url_inicial])
    paginas_visitadas: Set[str] = set()
    produtos_visitados: Set[str] = set()
    links_produto: List[str] = []

    while fila_paginas and len(paginas_visitadas) < limite_paginas and len(links_produto) < limite_produtos:
        url_atual = fila_paginas.popleft()
        if url_atual in paginas_visitadas:
            continue

        paginas_visitadas.add(url_atual)
        resposta = baixar_html(url_atual)
        if not resposta.get("ok"):
            continue

        html = resposta.get("html", "")
        url_final = _normalizar_url(resposta.get("url", url_atual))
        classificacao = classificar_pagina(html, url_final)

        if classificacao.get("is_product"):
            if url_final not in produtos_visitados:
                produtos_visitados.add(url_final)
                links_produto.append(url_final)
            continue

        for link in _coletar_links(html, url_final):
            if link in paginas_visitadas:
                continue

            if _eh_link_produto(link):
                if link not in produtos_visitados:
                    produtos_visitados.add(link)
                    links_produto.append(link)
                continue

            if _eh_link_categoria(link) or _eh_link_paginacao(link):
                fila_paginas.append(link)

    if not links_produto and url_inicial not in produtos_visitados:
        primeira = baixar_html(url_inicial)
        if primeira.get("ok"):
            html = primeira.get("html", "")
            url_final = _normalizar_url(primeira.get("url", url_inicial))
            classificacao = classificar_pagina(html, url_final)
            if classificacao.get("is_product"):
                links_produto.append(url_final)

    produtos: List[Dict] = []

    for url_produto in links_produto[:limite_produtos]:
        resposta = baixar_html(url_produto)
        if not resposta.get("ok"):
            produtos.append(_linha_erro(url_produto, str(resposta.get("erro", "Falha ao baixar HTML."))))
            continue

        try:
            linha = extrair_produto_html(resposta.get("html", ""), resposta.get("url", url_produto))
            linha["origem_tipo"] = "scraper_site"
            linha["origem_arquivo_ou_url"] = resposta.get("url", url_produto)
            linha["erro_scraper"] = ""
            produtos.append(linha)
        except Exception as e:
            produtos.append(_linha_erro(url_produto, str(e)))

    produtos = _deduplicar_produtos(produtos)

    if not produtos:
        produtos = [_linha_erro(url_inicial, "A varredura terminou sem produtos válidos.")]

    return _garantir_colunas(pd.DataFrame(produtos))
