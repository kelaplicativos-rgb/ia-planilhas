
from __future__ import annotations

import re
import time
from collections import deque
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    extrair_preco,
    fornecedor_cfg,
    normalizar_texto,
    normalizar_url,
    safe_str,
)
from bling_app_zero.core.site_crawler_config import ROTAS_INICIAIS_PADRAO
from bling_app_zero.core.site_crawler_http import (
    fetch_html_retry,
    normalizar_link_crawl,
    url_valida_para_crawl,
)


# ============================================================
# HELPERS DE AUTENTICAÇÃO
# ============================================================

def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False
    return bool(auth_context.get("session_ready", False))


def _normalizar_headers_auth(headers: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}

    saida: dict[str, str] = {}
    for chave, valor in headers.items():
        k = safe_str(chave)
        v = safe_str(valor)
        if k and v:
            saida[k] = v
    return saida


def _criar_sessao_autenticada(auth_context: dict[str, Any] | None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )

    if not _auth_context_valido(auth_context):
        return session

    headers = _normalizar_headers_auth(auth_context.get("headers"))
    if headers:
        session.headers.update(headers)

    cookies = auth_context.get("cookies", [])
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue

            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"

            if not nome:
                continue

            try:
                session.cookies.set(
                    nome,
                    valor,
                    domain=dominio or None,
                    path=path,
                )
            except Exception:
                continue

    return session


def _fetch_html_com_contexto(url: str, auth_context: dict[str, Any] | None = None) -> str:
    url = safe_str(url)
    if not url:
        return ""

    if _auth_context_valido(auth_context):
        session = _criar_sessao_autenticada(auth_context)
        ultima_exc: Exception | None = None

        for _ in range(2):
            try:
                response = session.get(url, timeout=45, allow_redirects=True)
                if response.ok and safe_str(response.text):
                    return safe_str(response.text)
                ultima_exc = RuntimeError(f"HTTP {response.status_code}")
            except Exception as exc:
                ultima_exc = exc

        if ultima_exc is not None:
            raise ultima_exc

    return safe_str(fetch_html_retry(url, tentativas=2))


def _products_url_contexto(base_url: str, auth_context: dict[str, Any] | None = None) -> str:
    if isinstance(auth_context, dict):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            return normalizar_url(products_url)
    return normalizar_url(base_url)


def _detectar_links_em_texto_solto(base_url: str, html: str) -> list[str]:
    html = safe_str(html)
    encontrados: list[str] = []
    vistos: set[str] = set()

    if not html:
        return encontrados

    padroes = [
        r'https?://[^"\']+',
        r'\/admin\/products\/[^"\']+',
        r'\/produto\/[^"\']+',
        r'\/product\/[^"\']+',
        r'\/p\/[^"\']+',
        r'\/item\/[^"\']+',
        r'\/sku\/[^"\']+',
    ]

    for padrao in padroes:
        for match in re.findall(padrao, html, flags=re.IGNORECASE):
            url = normalizar_link_crawl(base_url, safe_str(match))
            if not url_valida_para_crawl(base_url, url):
                continue
            if url in vistos:
                continue
            vistos.add(url)
            encontrados.append(url)

    return encontrados


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def classificar_link(base_url: str, url: str, texto_ancora: str = "", bloco: str = "") -> str:
    cfg = fornecedor_cfg(base_url)
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto_ancora)
    bloco_n = normalizar_texto(bloco)

    hints_produto = cfg.get(
        "produto_hints",
        [
            "/produto",
            "/product",
            "/p/",
            "/item/",
            "/sku/",
            "/prd/",
            "/admin/products/",
            "/products/",
            "/produto/",
        ],
    )
    hints_categoria = cfg.get(
        "categoria_hints",
        [
            "/categoria",
            "/categorias",
            "/collections/",
            "/departamento",
            "/busca",
            "/search",
            "/admin/products",
            "/products",
        ],
    )

    score_produto = 0
    score_categoria = 0

    if any(h in url_n for h in hints_produto):
        score_produto += 4

    if any(h in url_n for h in hints_categoria):
        score_categoria += 4

    if re.search(r"/p/\d+|/produto/|/product/|/sku/|/item/|/admin/products/\d+", url_n):
        score_produto += 3

    if re.search(r"/categoria/|/categorias/|/collections?/|/departamentos?/|/admin/products/?$", url_n):
        score_categoria += 3

    if any(t in texto_n for t in ["comprar", "ver produto", "detalhes", "sku", "código", "codigo"]):
        score_produto += 2

    if any(t in texto_n for t in ["categoria", "departamento", "coleção", "colecao", "produtos"]):
        score_categoria += 2

    if extrair_preco(bloco_n):
        score_produto += 1

    if any(t in bloco_n for t in ["adicionar ao carrinho", "comprar agora", "parcel", "r$"]):
        score_produto += 1

    if any(t in bloco_n for t in ["estoque", "sku", "ean", "gtin", "marca", "categoria"]):
        score_produto += 1

    if "page=" in url_n or "/page/" in url_n or "p=" in url_n:
        score_categoria += 2

    if score_produto >= max(3, score_categoria):
        return "produto"

    if score_categoria >= 2:
        return "categoria"

    return "indefinido"


def eh_paginacao(url: str, texto: str = "") -> bool:
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto)

    if any(x in url_n for x in ["page=", "/page/", "?p=", "&p=", "offset=", "pagina=", "pag="]):
        return True

    if re.search(r"/page/\d+", url_n):
        return True

    if texto_n in {"1", "2", "3", "4", "5", "próxima", "proxima", "next", ">", ">>"}:
        return True

    if any(x in texto_n for x in ["próxima", "proxima", "next", "avançar", "avancar", "mais", "carregar mais"]):
        return True

    return False


def _eh_link_login_ou_sistema(url: str, texto: str = "", bloco: str = "") -> bool:
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto)
    bloco_n = normalizar_texto(bloco)

    sinais_ruins = [
        "/login",
        "/logout",
        "/conta",
        "/account",
        "/register",
        "/cadastro",
        "/esqueci-senha",
        "/forgot",
        "/reset-password",
        "/politica",
        "/privacy",
        "/termos",
        "/terms",
        "/suporte",
        "/support",
        "/whatsapp",
        "mailto:",
        "tel:",
        "javascript:",
    ]

    if any(x in url_n for x in sinais_ruins):
        return True

    if any(x in texto_n for x in ["entrar", "login", "sair", "minha conta", "esqueci minha senha"]):
        return True

    if any(x in bloco_n for x in ["recaptcha", "não sou um robô", "nao sou um robo"]):
        return True

    return False


# ============================================================
# EXTRAÇÃO
# ============================================================

def extrair_produtos_de_cards(base_url: str, soup: BeautifulSoup) -> list[str]:
    links_produto = []
    vistos = set()

    seletores_cards = [
        "[class*='product']",
        "[class*='produto']",
        "[class*='item']",
        "[class*='card']",
        "[data-product]",
        "[data-id]",
        "li",
        "article",
        "div",
        "tr",
    ]

    for seletor in seletores_cards:
        try:
            cards = soup.select(seletor)
        except Exception:
            cards = []

        for card in cards:
            try:
                bloco = card.get_text(" ", strip=True)[:2000]
            except Exception:
                bloco = ""

            bloco_n = normalizar_texto(bloco)
            if not bloco_n:
                continue

            possui_sinal_produto = False

            if extrair_preco(bloco):
                possui_sinal_produto = True

            if any(
                x in bloco_n
                for x in [
                    "comprar",
                    "carrinho",
                    "adicionar",
                    "parcel",
                    "sku",
                    "código",
                    "codigo",
                    "produto",
                    "estoque",
                    "ean",
                    "gtin",
                    "marca",
                ]
            ):
                possui_sinal_produto = True

            if not possui_sinal_produto:
                continue

            anchors = card.select("a[href]")
            for a in anchors:
                href = safe_str(a.get("href"))
                url = normalizar_link_crawl(base_url, href)
                if not url_valida_para_crawl(base_url, url):
                    continue

                texto = " ".join(a.stripped_strings).strip()
                if _eh_link_login_ou_sistema(url, texto, bloco):
                    continue

                classe = classificar_link(base_url, url, texto, bloco)

                if classe == "produto" or possui_sinal_produto:
                    if url not in vistos:
                        vistos.add(url)
                        links_produto.append(url)

    return links_produto


def extrair_links_pagina(base_url: str, url_pagina: str, html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")

    links_categoria = []
    links_produto = []
    vistos_categoria = set()
    vistos_produto = set()

    produtos_card = extrair_produtos_de_cards(base_url, soup)
    for url in produtos_card:
        if url not in vistos_produto:
            vistos_produto.add(url)
            links_produto.append(url)

    for a in soup.find_all("a", href=True):
        href = safe_str(a.get("href"))
        if not href:
            continue

        url = normalizar_link_crawl(base_url, href)
        if not url_valida_para_crawl(base_url, url):
            continue

        texto = " ".join(a.stripped_strings).strip()
        bloco = ""
        try:
            bloco = a.parent.get_text(" ", strip=True)[:1500]
        except Exception:
            bloco = texto

        if _eh_link_login_ou_sistema(url, texto, bloco):
            continue

        if eh_paginacao(url, texto):
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)
            continue

        classe = classificar_link(base_url, url, texto, bloco)

        possui_sinal_produto = (
            bool(extrair_preco(bloco))
            or any(
                x in normalizar_texto(bloco)
                for x in [
                    "r$",
                    "comprar",
                    "carrinho",
                    "parcel",
                    "sku",
                    "código",
                    "codigo",
                    "estoque",
                    "ean",
                    "gtin",
                ]
            )
        )

        if classe == "produto" or possui_sinal_produto:
            if url not in vistos_produto:
                vistos_produto.add(url)
                links_produto.append(url)
            continue

        if classe == "categoria":
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)
            continue

        if url not in vistos_categoria:
            vistos_categoria.add(url)
            links_categoria.append(url)

    for url_solta in _detectar_links_em_texto_solto(base_url, html):
        if _eh_link_login_ou_sistema(url_solta):
            continue

        classe = classificar_link(base_url, url_solta, "", html[:1000])

        if classe == "produto":
            if url_solta not in vistos_produto:
                vistos_produto.add(url_solta)
                links_produto.append(url_solta)
        elif url_solta not in vistos_categoria:
            vistos_categoria.add(url_solta)
            links_categoria.append(url_solta)

    if url_pagina not in vistos_categoria and classificar_link(base_url, url_pagina) == "categoria":
        links_categoria.insert(0, url_pagina)

    return links_categoria, links_produto


# ============================================================
# ROTAS INICIAIS
# ============================================================

def rotas_iniciais(
    base_url: str,
    termo: str = "",
    auth_context: dict[str, Any] | None = None,
) -> list[str]:
    base = normalizar_url(base_url)
    alvo_base = _products_url_contexto(base, auth_context)

    urls = [f"{base}{rota}" for rota in ROTAS_INICIAIS_PADRAO]

    if alvo_base and alvo_base != base:
        urls.insert(0, alvo_base)

    termo = safe_str(termo)
    if termo:
        q = quote_plus(termo)
        slug = re.sub(r"[^a-z0-9]+", "-", normalizar_texto(termo)).strip("-")
        urls.extend(
            [
                f"{base}/search?q={q}",
                f"{base}/busca?q={q}",
                f"{base}/busca?search={q}",
                f"{base}/catalogsearch/result/?q={q}",
                f"{base}/categoria/{slug}",
                f"{base}/?s={q}",
            ]
        )

    if _auth_context_valido(auth_context):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            urls.extend(
                [
                    products_url,
                    f"{products_url}?page=1",
                    f"{products_url}?pagina=1",
                    f"{products_url}?p=1",
                    f"{products_url}?offset=0",
                ]
            )

    vistos = set()
    saida = []
    for url in urls:
        url = normalizar_link_crawl(base, url)
        if url and url not in vistos:
            vistos.add(url)
            saida.append(url)

    return saida


# ============================================================
# DESCOBERTA PRINCIPAL
# ============================================================

def descobrir_produtos_no_dominio(
    base_url: str,
    termo: str = "",
    max_paginas: int = 400,
    max_produtos: int = 8000,
    max_segundos: int = 900,
    auth_context: dict[str, Any] | None = None,
) -> list[str]:
    inicio = time.time()

    fila = deque(rotas_iniciais(base_url, termo=termo, auth_context=auth_context))
    paginas_visitadas = set()
    produtos_encontrados = []
    produtos_vistos = set()

    while fila:
        if len(paginas_visitadas) >= max_paginas:
            break
        if len(produtos_encontrados) >= max_produtos:
            break
        if time.time() - inicio > max_segundos:
            break

        url_atual = fila.popleft()
        if url_atual in paginas_visitadas:
            continue

        paginas_visitadas.add(url_atual)

        try:
            html = _fetch_html_com_contexto(url_atual, auth_context=auth_context)
        except Exception:
            continue

        if not html:
            continue

        links_categoria, links_produto = extrair_links_pagina(base_url, url_atual, html)

        for url_produto in links_produto:
            if url_produto not in produtos_vistos:
                produtos_vistos.add(url_produto)
                produtos_encontrados.append(url_produto)
                if len(produtos_encontrados) >= max_produtos:
                    break

        for url_categoria in links_categoria:
            if url_categoria not in paginas_visitadas and url_categoria not in fila:
                fila.append(url_categoria)

    if not produtos_encontrados and _auth_context_valido(auth_context):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            url_fallback = normalizar_link_crawl(base_url, products_url)
            if url_fallback:
                produtos_encontrados.append(url_fallback)

    return produtos_encontrados
