from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

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
    "/produtos/",
    "/product",
    "/products/",
    "/p/",
    "/pd-",
    "/item/",
    "/sku/",
    "/loja/produto",
)

CATEGORY_HINTS = (
    "/categoria",
    "/categorias",
    "/category",
    "/categories",
    "/departamento",
    "/colecao",
    "/colecoes",
    "/collections",
    "/catalog",
    "/catalogo",
    "/loja/",
)

PAGINATION_TOKENS = (
    "page=",
    "pagina=",
    "paged=",
    "p=",
    "?pg=",
    "?page=",
    "&page=",
    "&pagina=",
    "/page/",
)


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").strip().lower()
    path = parsed.path or "/"

    return urlunparse((scheme, netloc, path, "", parsed.query, "")).rstrip("/")


def _mesmo_dominio(url_base: str, url_destino: str) -> bool:
    base_host = (urlparse(url_base).netloc or "").lower().replace("www.", "")
    dest_host = (urlparse(url_destino).netloc or "").lower().replace("www.", "")
    return bool(base_host) and base_host == dest_host


def _limpar_fragmentos_e_trackers(url: str) -> str:
    parsed = urlparse(url)
    query_items = []
    for chave, valor in parse_qsl(parsed.query, keep_blank_values=True):
        chave_lower = (chave or "").lower()
        if chave_lower.startswith("utm_"):
            continue
        if chave_lower in {"gclid", "fbclid"}:
            continue
        query_items.append((chave, valor))

    query = urlencode(query_items, doseq=True)
    path = parsed.path or "/"

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            query,
            "",
        )
    ).rstrip("/")


def _texto_link(a) -> str:
    try:
        return (a.get_text(" ", strip=True) or "").strip().lower()
    except Exception:
        return ""


def _eh_link_produto(url: str, texto_ancora: str = "") -> bool:
    url_baixa = (url or "").lower()
    texto_ancora = (texto_ancora or "").lower()

    if any(token in url_baixa for token in PRODUCT_HINTS):
        return True

    if any(
        token in texto_ancora
        for token in (
            "comprar",
            "ver produto",
            "detalhes",
            "saiba mais",
            "escolher opções",
            "opções",
        )
    ):
        return True

    return False


def _eh_link_categoria(url: str, texto_ancora: str = "") -> bool:
    url_baixa = (url or "").lower()
    texto_ancora = (texto_ancora or "").lower()

    if any(token in url_baixa for token in CATEGORY_HINTS):
        return True

    if any(
        token in texto_ancora
        for token in (
            "categoria",
            "departamento",
            "coleção",
            "colecao",
            "ver mais",
            "mostrar mais",
        )
    ):
        return True

    return False


def _eh_link_paginacao(url: str, texto_ancora: str = "") -> bool:
    url_baixa = (url or "").lower()
    texto_ancora = (texto_ancora or "").lower()

    if any(token in url_baixa for token in PAGINATION_TOKENS):
        return True

    if texto_ancora in {
        "2", "3", "4", "5", "6", "7", "8", "9", "10",
        "próxima", "proxima", "next", "avançar", "avancar",
    }:
        return True

    return False


def _coletar_links(html: str, url_base: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: List[Tuple[str, str]] = []
    vistos: Set[str] = set()

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href:
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absoluto = urljoin(url_base, href)
        absoluto = _normalizar_url(_limpar_fragmentos_e_trackers(absoluto))
        if not absoluto:
            continue
        if not _mesmo_dominio(url_base, absoluto):
            continue
        if absoluto in vistos:
            continue

        vistos.add(absoluto)
        links.append((absoluto, _texto_link(a)))

    return links


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
                str(item.get("codigo", "")).strip().lower(),
                str(item.get("nome", "")).strip().lower(),
                str(item.get("gtin", "")).strip(),
                str(item.get("origem_arquivo_ou_url", "")).strip().lower(),
            ]
        )

        chave_secundaria = "|".join(
            [
                str(item.get("codigo", "")).strip().lower(),
                str(item.get("nome", "")).strip().lower(),
                str(item.get("gtin", "")).strip(),
            ]
        )

        chave_final = chave_secundaria if chave_secundaria.strip("|") else chave

        if chave_final in vistos:
            continue

        vistos.add(chave_final)
        saida.append(item)

    return saida


def _pontuar_link(url: str, texto_ancora: str) -> int:
    score = 0
    url_baixa = (url or "").lower()
    texto_ancora = (texto_ancora or "").lower()

    if _eh_link_produto(url_baixa, texto_ancora):
        score += 5

    if _eh_link_categoria(url_baixa, texto_ancora):
        score += 2

    if _eh_link_paginacao(url_baixa, texto_ancora):
        score += 1

    if any(token in url_baixa for token in (".jpg", ".jpeg", ".png", ".webp", ".svg", ".pdf")):
        score -= 10

    if any(token in url_baixa for token in ("/cart", "/carrinho", "/checkout", "/login", "/account")):
        score -= 10

    return score


def _normalizar_estoque(valor_estoque: object, disponibilidade: object) -> str:
    estoque_txt = str(valor_estoque or "").strip()
    disp_txt = str(disponibilidade or "").strip().lower()

    if estoque_txt:
        txt = estoque_txt.lower()
        if txt in {"sem estoque", "indisponível", "indisponivel", "zerado", "esgotado"}:
            return "0"
        return estoque_txt

    if any(token in disp_txt for token in ("sem estoque", "indisponível", "indisponivel", "zerado", "esgotado")):
        return "0"

    return ""


def _pos_processar_linha(linha: Dict, url_final: str) -> Dict:
    linha = dict(linha or {})

    for coluna in COLUNAS_PADRAO:
        linha.setdefault(coluna, "")

    linha["origem_tipo"] = "scraper_site"
    linha["origem_arquivo_ou_url"] = url_final
    linha["erro_scraper"] = str(linha.get("erro_scraper", "") or "").strip()

    nome = str(linha.get("nome", "") or "").strip()
    descricao = str(linha.get("descricao", "") or "").strip()
    descricao_curta = str(linha.get("descricao_curta", "") or "").strip()

    if not nome and descricao:
        linha["nome"] = descricao

    if not linha["descricao"] and linha["nome"]:
        linha["descricao"] = linha["nome"]

    if not descricao_curta and linha["descricao"]:
        linha["descricao_curta"] = linha["descricao"]

    linha["estoque"] = _normalizar_estoque(
        linha.get("estoque", ""),
        linha.get("disponibilidade_site", ""),
    )

    return linha


def extrair_produtos_de_site(
    url_inicial: str,
    limite_paginas: int = 60,
    limite_produtos: int = 200,
) -> pd.DataFrame:
    """
    Varre o site a partir de uma URL inicial, identifica páginas de produto
    e extrai os dados usando o extrator existente.

    Mantém a assinatura original para compatibilidade com o restante do sistema.
    """
    url_inicial = _normalizar_url(url_inicial)
    if not url_inicial:
        return _garantir_colunas(pd.DataFrame([_linha_erro("", "URL inválida.")]))

    fila_paginas = deque([url_inicial])
    paginas_visitadas: Set[str] = set()
    produtos_visitados: Set[str] = set()
    links_produto: List[str] = []

    while fila_paginas and len(paginas_visitadas) < limite_paginas and len(links_produto) < limite_produtos:
        url_atual = fila_paginas.popleft()
        if not url_atual or url_atual in paginas_visitadas:
            continue

        paginas_visitadas.add(url_atual)

        resposta = baixar_html(url_atual)
        if not resposta.get("ok"):
            continue

        html = resposta.get("html", "") or ""
        url_final = _normalizar_url(str(resposta.get("url", url_atual) or url_atual))

        classificacao = classificar_pagina(html, url_final)

        if classificacao.get("is_product"):
            if url_final not in produtos_visitados:
                produtos_visitados.add(url_final)
                links_produto.append(url_final)
            continue

        candidatos_links = _coletar_links(html, url_final)
        candidatos_ordenados = sorted(
            candidatos_links,
            key=lambda item: _pontuar_link(item[0], item[1]),
            reverse=True,
        )

        for link, texto_ancora in candidatos_ordenados:
            if len(links_produto) >= limite_produtos:
                break

            if link in paginas_visitadas:
                continue

            if _eh_link_produto(link, texto_ancora):
                if link not in produtos_visitados:
                    produtos_visitados.add(link)
                    links_produto.append(link)
                continue

            if _eh_link_categoria(link, texto_ancora) or _eh_link_paginacao(link, texto_ancora):
                fila_paginas.append(link)

    if not links_produto and url_inicial not in produtos_visitados:
        primeira = baixar_html(url_inicial)
        if primeira.get("ok"):
            html = primeira.get("html", "") or ""
            url_final = _normalizar_url(str(primeira.get("url", url_inicial) or url_inicial))
            classificacao = classificar_pagina(html, url_final)
            if classificacao.get("is_product"):
                links_produto.append(url_final)

    produtos: List[Dict] = []

    for url_produto in links_produto[:limite_produtos]:
        resposta = baixar_html(url_produto)
        if not resposta.get("ok"):
            produtos.append(
                _linha_erro(
                    url_produto,
                    str(resposta.get("erro", "Falha ao baixar HTML.")),
                )
            )
            continue

        try:
            url_final = _normalizar_url(str(resposta.get("url", url_produto) or url_produto))
            linha = extrair_produto_html(resposta.get("html", "") or "", url_final)
            linha = _pos_processar_linha(linha, url_final)
            produtos.append(linha)
        except Exception as e:
            produtos.append(_linha_erro(url_produto, str(e)))

    produtos = _deduplicar_produtos(produtos)

    if not produtos:
        produtos = [_linha_erro(url_inicial, "A varredura terminou sem produtos válidos.")]

    return _garantir_colunas(pd.DataFrame(produtos))
