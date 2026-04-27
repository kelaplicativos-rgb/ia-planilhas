from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from .crawler_dispatcher import fetch_html, normalizar_url, precisa_playwright
from .http_client import build_session
from .sitemap_engine import discover_links_from_sitemap
from .link_discovery import (
    extract_category_links,
    extract_pagination_links,
    extract_product_links,
)
from .product_extractor import extract_product_from_page
from .product_normalizer import normalize_products, to_dataframe
from .crawler_utils import log


def _dedupe_links(links: List[str]) -> List[str]:
    vistos = set()
    saida = []

    for link in links:
        link = normalizar_url(link)
        if not link:
            continue
        if link in vistos:
            continue
        vistos.add(link)
        saida.append(link)

    return saida


def _parece_produto(link: str) -> bool:
    link_l = str(link or "").lower()
    pistas = [
        "/produto",
        "/produtos",
        "/product",
        "/products",
        "/p/",
        "/item/",
        "produto=",
        "product_id=",
        "sku=",
    ]
    return any(p in link_l for p in pistas)


def _limitar(links: List[str], limite: Optional[int]) -> List[str]:
    try:
        limite_int = int(limite) if limite is not None else 0
    except Exception:
        limite_int = 0

    if limite_int > 0:
        return links[:limite_int]

    return links


def _int_seguro(valor, default: int = 0) -> int:
    try:
        if valor is None or valor == "":
            return default
        return int(valor)
    except Exception:
        return default


def run_crawler(
    url: str,
    *,
    auth_context: Optional[Dict] = None,
    varrer_site_completo: bool = True,
    sitemap_completo: bool = True,
    max_workers: int = 8,
    limite: Optional[int] = None,
    limite_paginas: Optional[int] = None,
    usar_sitemap: bool = True,
    usar_home: bool = True,
    usar_categoria: bool = True,
    modo: str = "completo",
    preferir_playwright: Optional[bool] = None,
    **kwargs,
) -> pd.DataFrame:
    url = normalizar_url(url)
    if not url:
        return pd.DataFrame()

    session = build_session(auth_context)

    js_primeiro = precisa_playwright(url) if preferir_playwright is None else bool(preferir_playwright)

    log(
        "[ENGINE V3] iniciando crawler "
        f"| url={url} "
        f"| js_primeiro={js_primeiro} "
        f"| varrer_site_completo={varrer_site_completo} "
        f"| sitemap_completo={sitemap_completo}"
    )

    product_links: List[str] = []
    pages_to_visit: List[str] = []

    if usar_home:
        pages_to_visit.append(url)

    if sitemap_completo and usar_sitemap:
        try:
            sitemap_links = discover_links_from_sitemap(session, url)
        except Exception as exc:
            log(f"[ENGINE V3] sitemap falhou → {exc}")
            sitemap_links = []

        for link in sitemap_links:
            if _parece_produto(link):
                product_links.append(link)
            else:
                pages_to_visit.append(link)

        log(f"[ENGINE V3] sitemap → {len(sitemap_links)} links")

    product_links = _dedupe_links(product_links)
    pages_to_visit = _dedupe_links(pages_to_visit)

    visited = set()
    paginas_visitadas = 0
    limite_paginas_int = _int_seguro(limite_paginas, 0)

    while pages_to_visit:
        page = pages_to_visit.pop(0)
        page = normalizar_url(page)

        if not page or page in visited:
            continue

        visited.add(page)
        paginas_visitadas += 1

        if limite_paginas_int > 0 and paginas_visitadas > limite_paginas_int:
            break

        html = fetch_html(
            session,
            page,
            auth_context=auth_context,
            preferir_playwright=js_primeiro,
        )

        if not html:
            continue

        novos_produtos = extract_product_links(html, page)
        product_links += novos_produtos

        if usar_categoria:
            pages_to_visit += extract_category_links(html, page)

        pages_to_visit += extract_pagination_links(html, page)

        product_links = _dedupe_links(product_links)
        pages_to_visit = _dedupe_links(pages_to_visit)

        log(
            "[ENGINE V3] página lida "
            f"| visitadas={paginas_visitadas} "
            f"| produtos={len(product_links)} "
            f"| fila={len(pages_to_visit)}"
        )

        if not varrer_site_completo and len(product_links) >= 200:
            break

        if limite is not None and _int_seguro(limite, 0) > 0 and len(product_links) >= _int_seguro(limite, 0):
            break

    product_links = _limitar(_dedupe_links(product_links), limite)

    log(f"[ENGINE V3] links de produtos encontrados → {len(product_links)}")

    produtos: List[Dict] = []

    if not product_links:
        log("[ENGINE V3] nenhum link encontrado; tentando extrair produto da própria URL.")
        html_home = fetch_html(
            session,
            url,
            auth_context=auth_context,
            preferir_playwright=True,
        )

        produto_home = extract_product_from_page(html_home, url)

        if produto_home and produto_home.get("nome"):
            produtos.append(produto_home)

    for i, link in enumerate(product_links, start=1):
        try:
            html = fetch_html(
                session,
                link,
                auth_context=auth_context,
                preferir_playwright=js_primeiro,
            )

            produto = extract_product_from_page(html, link)

            if produto and produto.get("nome"):
                produtos.append(produto)

        except Exception as exc:
            log(f"[ENGINE V3 ERRO PRODUTO] {link} → {exc}")

        if i % 10 == 0 or i == len(product_links):
            log(f"[ENGINE V3] produtos processados {i}/{len(product_links)}")

    produtos = normalize_products(produtos)
    df = to_dataframe(produtos)

    log(f"[ENGINE V3] finalizado → {len(df)} produto(s) úteis")

    return df
