from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers_text import (
    normalizar_url_crawler,
    url_mesmo_dominio_crawler,
)


def link_parece_produto_crawler(url: str) -> bool:
    u = (url or "").lower()

    if any(
        x in u
        for x in [
            "javascript:",
            "mailto:",
            "#",
            "login",
            "conta",
            "carrinho",
            "checkout",
            "categoria",
            "category",
        ]
    ):
        return False

    sinais = [
        "/produto",
        "/product",
        "/p/",
        "/prod/",
        "/item/",
        "/sku/",
        "produto-",
        "product-",
    ]
    return any(s in u for s in sinais)


def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        url = normalizar_url_crawler(base_url, href)
        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        u = url.lower()

        if any(
            x in u
            for x in [
                "login",
                "conta",
                "carrinho",
                "checkout",
                "categoria",
                "category",
                "blog",
                "javascript:",
                "#",
            ]
        ):
            continue

        if link_parece_produto_crawler(url):
            links.append(url)
            continue

        path = urlparse(u).path or ""
        partes = [p for p in path.split("/") if p.strip()]

        if (
            len(u) > 30
            and "-" in u
            and len(partes) >= 1
            and not u.endswith((".jpg", ".png", ".svg", ".webp", ".jpeg"))
        ):
            links.append(url)

    return list(dict.fromkeys(links))[:300]


def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        url = normalizar_url_crawler(base_url, a.get("href"))
        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(
            x in url.lower()
            for x in [
                "page=",
                "pagina",
                "/page/",
                "/pagina/",
                "?p=",
                "&p=",
                "pg=",
                "offset",
                "start",
            ]
        ):
            links.append(url)

    return list(dict.fromkeys(links))
