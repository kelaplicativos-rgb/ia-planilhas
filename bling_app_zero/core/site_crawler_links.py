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
# CONSTANTES / SINAIS
# ============================================================

PRODUCT_HINTS_DEFAULT = [
    "/produto",
    "/product",
    "/p/",
    "/item/",
    "/sku/",
    "/prd/",
    "/products/",
]

CATEGORY_HINTS_DEFAULT = [
    "/categoria",
    "/categorias",
    "/collections/",
    "/collection/",
    "/departamento",
    "/busca",
    "/search",
]

BLOCK_PAGE_HINTS = [
    "cloudflare",
    "attention required",
    "verify you are human",
    "checking your browser",
    "access denied",
    "forbidden",
    "captcha",
    "g-recaptcha",
    "hcaptcha",
]

PRODUCT_TEXT_HINTS = [
    '"@type":"product"',
    '"@type": "product"',
    '"@type":"Product"',
    '"@type": "Product"',
    "application/ld+json",
    "adicionar ao carrinho",
    "add to cart",
    "comprar agora",
    "buy now",
    "sku",
    "código",
    "codigo",
    "gtin",
    "ean",
    "r$",
    "price",
    "availability",
    "in stock",
    "out of stock",
    "itemprop=\"price\"",
    "itemprop='price'",
    "itemprop=\"sku\"",
    "itemprop='sku'",
    "produto",
    "product",
]


# ============================================================
# HELPERS DE AUTENTICAÇÃO
# ============================================================

def _auth_context_tem_dados_http(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    auth_http_ok = bool(auth_context.get("auth_http_ok", False))
    cookies = auth_context.get("cookies")
    cookies_count = int(auth_context.get("cookies_count", 0) or 0)

    tem_cookies = isinstance(cookies, list) and len(cookies) > 0

    return bool(auth_http_ok and (tem_cookies or cookies_count > 0))


def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    if not _auth_context_tem_dados_http(auth_context):
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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
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


def _products_url_contexto(base_url: str, auth_context: dict[str, Any] | None = None) -> str:
    if isinstance(auth_context, dict):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            return normalizar_url(products_url)
    return normalizar_url(base_url)


def _expandir_urls_tentativa(url: str) -> list[str]:
    url = normalizar_url(url)
    if not url:
        return []

    urls = [url]

    if url.endswith("/"):
        urls.append(url.rstrip("/"))
    else:
        urls.append(url + "/")

    if url.startswith("https://"):
        urls.append("http://" + url[len("https://"):])
    elif url.startswith("http://"):
        urls.append("https://" + url[len("http://"):])

    saida: list[str] = []
    vistos: set[str] = set()
    for item in urls:
        item_n = safe_str(item)
        if item_n and item_n not in vistos:
            vistos.add(item_n)
            saida.append(item_n)
    return saida


def _fetch_html_publico(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""

    ultima_exc: Exception | None = None

    for url_tentativa in _expandir_urls_tentativa(url):
        if fetch_html_retry is not None:
            for tentativas in (2, 3):
                try:
                    html_retry = safe_str(fetch_html_retry(url_tentativa, tentativas=tentativas))
                    if html_retry:
                        return html_retry
                except Exception as exc:
                    ultima_exc = exc

        for headers in (
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Mobile Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        ):
            for verify in (True, False):
                try:
                    response = requests.get(
                        url_tentativa,
                        headers=headers,
                        timeout=35,
                        allow_redirects=True,
                        verify=verify,
                    )
                    if response.ok and safe_str(response.text):
                        return safe_str(response.text)
                except Exception as exc:
                    ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return ""


def _fetch_html_com_contexto(url: str, auth_context: dict[str, Any] | None = None) -> str:
    url = safe_str(url)
    if not url:
        return ""

    if _auth_context_valido(auth_context):
        session = _criar_sessao_autenticada(auth_context)
        ultima_exc: Exception | None = None

        for url_tentativa in _expandir_urls_tentativa(url):
            for _ in range(2):
                try:
                    response = session.get(url_tentativa, timeout=45, allow_redirects=True)
                    if response.ok and safe_str(response.text):
                        html = safe_str(response.text)
                        if html:
                            return html
                    ultima_exc = RuntimeError(f"HTTP {response.status_code}")
                except Exception as exc:
                    ultima_exc = exc

        if ultima_exc is not None:
            try:
                return _fetch_html_publico(url)
            except Exception:
                raise ultima_exc

    return _fetch_html_publico(url)


def _detectar_links_em_texto_solto(base_url: str, html: str) -> list[str]:
    html = safe_str(html)
    encontrados: list[str] = []
    vistos: set[str] = set()

    if not html:
        return encontrados

    padroes = [
        r'https?://[^"\']+',
        r'\\/produto\\/[^"\']+',
        r'\\/product\\/[^"\']+',
        r'\\/p\\/[^"\']+',
        r'\\/item\\/[^"\']+',
        r'\\/sku\\/[^"\']+',
        r'\\/products\\/[^"\']+',
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

def _html_tem_sinais_de_bloqueio(html: str) -> bool:
    html_n = normalizar_texto(html)
    if not html_n:
        return False
    return any(x in html_n for x in BLOCK_PAGE_HINTS)


def _texto_tem_sinais_de_produto(texto: str) -> bool:
    texto_n = normalizar_texto(texto)
    if not texto_n:
        return False
    return any(x in texto_n for x in PRODUCT_TEXT_HINTS)


def _score_html_produto(html: str) -> int:
    html_n = normalizar_texto(html)
    if not html_n:
        return 0

    score = 0

    if '"@type":"product"' in html_n or '"@type": "product"' in html_n or '"@type":"product",' in html_n:
        score += 4

    if "adicionar ao carrinho" in html_n or "add to cart" in html_n or "comprar agora" in html_n:
        score += 2

    if "sku" in html_n or "gtin" in html_n or "ean" in html_n or "código" in html_n or "codigo" in html_n:
        score += 1

    if "r$" in html_n or "price" in html_n or "parcel" in html_n:
        score += 1

    if "og:type" in html_n and "product" in html_n:
        score += 2

    return score


def _score_url_produto(url: str, texto_ancora: str = "", bloco: str = "") -> int:
    cfg = fornecedor_cfg(url)
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto_ancora)
    bloco_n = normalizar_texto(bloco)

    hints_produto = cfg.get("produto_hints", PRODUCT_HINTS_DEFAULT)
    hints_categoria = cfg.get("categoria_hints", CATEGORY_HINTS_DEFAULT)

    score_produto = 0
    score_categoria = 0

    if any(h in url_n for h in hints_produto):
        score_produto += 4

    if any(h in url_n for h in hints_categoria):
        score_categoria += 4

    if re.search(r"/p/[\w\-]+|/produto/|/product/|/sku/|/item/", url_n):
        score_produto += 3

    if re.search(r"/categoria/|/categorias/|/collections?/|/departamentos?/", url_n):
        score_categoria += 3

    if any(t in texto_n for t in ["comprar", "ver produto", "detalhes", "sku", "código", "codigo"]):
        score_produto += 2

    if any(t in texto_n for t in ["categoria", "departamento", "coleção", "colecao", "produtos"]):
        score_categoria += 2

    if extrair_preco(bloco):
        score_produto += 1

    if any(t in bloco_n for t in ["adicionar ao carrinho", "comprar agora", "parcel", "r$"]):
        score_produto += 1

    if any(t in bloco_n for t in ["estoque", "sku", "ean", "gtin", "marca", "categoria"]):
        score_produto += 1

    if "page=" in url_n or "/page/" in url_n or "p=" in url_n:
        score_categoria += 2

    return score_produto - score_categoria


def classificar_link(base_url: str, url: str, texto_ancora: str = "", bloco: str = "") -> str:
    score = _score_url_produto(url, texto_ancora=texto_ancora, bloco=bloco)

    if score >= 3:
        return "produto"

    if score <= -1:
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


def _url_parece_produto(base_url: str, url: str, texto_ancora: str = "", bloco: str = "") -> bool:
    if not url_valida_para_crawl(base_url, url):
        return False

    url_n = normalizar_texto(url)
    if any(x in url_n for x in ["/login", "/conta", "/account", "/cart", "/checkout", "/carrinho"]):
        return False

    return _score_url_produto(url, texto_ancora=texto_ancora, bloco=bloco) >= 2


def _html_parece_produto_direto(url: str, html: str) -> bool:
    if not safe_str(url) or not safe_str(html):
        return False

    if _html_tem_sinais_de_bloqueio(html):
        return False

    score_url = _score_url_produto(url)
    score_html = _score_html_produto(html)

    if score_url >= 3 and score_html >= 1:
        return True

    if score_html >= 4:
        return True

    if _texto_tem_sinais_de_produto(html):
        return True

    return False


# ============================================================
# EXTRAÇÃO
# ============================================================

def extrair_produtos_de_cards(base_url: str, soup: BeautifulSoup) -> list[str]:
    links_produto: list[str] = []
    vistos: set[str] = set()

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

                if classe == "produto" or _url_parece_produto(base_url, url, texto, bloco):
                    if url not in vistos:
                        vistos.add(url)
                        links_produto.append(url)

    return links_produto


def extrair_links_pagina(base_url: str, url_pagina: str, html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")

    links_categoria: list[str] = []
    links_produto: list[str] = []
    vistos_categoria: set[str] = set()
    vistos_produto: set[str] = set()

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

        if classe == "produto" or _url_parece_produto(base_url, url, texto, bloco) or possui_sinal_produto:
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

        if classe == "produto" or _url_parece_produto(base_url, url_solta, "", html[:1000]):
            if url_solta not in vistos_produto:
                vistos_produto.add(url_solta)
                links_produto.append(url_solta)
        elif url_solta not in vistos_categoria:
            vistos_categoria.add(url_solta)
            links_categoria.append(url_solta)

    if (
        url_pagina not in vistos_categoria
        and classificar_link(base_url, url_pagina) == "categoria"
        and not _html_parece_produto_direto(url_pagina, html)
    ):
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

    urls = [base]

    for rota in ROTAS_INICIAIS_PADRAO:
        try:
            urls.append(f"{base}{rota}")
        except Exception:
            continue

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

    vistos: set[str] = set()
    saida: list[str] = []
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

    base_url = normalizar_url(base_url)
    fila = deque(rotas_iniciais(base_url, termo=termo, auth_context=auth_context))
    paginas_visitadas: set[str] = set()
    produtos_encontrados: list[str] = []
    produtos_vistos: set[str] = set()

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

        if _html_parece_produto_direto(url_atual, html):
            if url_atual not in produtos_vistos:
                produtos_vistos.add(url_atual)
                produtos_encontrados.append(url_atual)
                if len(produtos_encontrados) >= max_produtos:
                    break

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

    if not produtos_encontrados:
        try:
            html_base = _fetch_html_com_contexto(base_url, auth_context=auth_context)
            if _html_parece_produto_direto(base_url, html_base):
                produtos_encontrados.append(base_url)
        except Exception:
            pass

    if not produtos_encontrados and _auth_context_valido(auth_context):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            url_fallback = normalizar_link_crawl(base_url, products_url)
            if url_fallback:
                produtos_encontrados.append(url_fallback)

    return produtos_encontrados
