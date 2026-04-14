from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    meta_content_crawler,
    todas_imagens_crawler,
)
from bling_app_zero.core.site_crawler_extractors_utils import (
    _adicionar_url_imagem,
    _filtrar_imagens,
    _safe_str,
)

PRODUCT_IMAGE_SELECTORS = [
    ".woocommerce-product-gallery img",
    ".product-gallery img",
    ".product__gallery img",
    ".product-gallery__image img",
    ".produto-galeria img",
    ".galeria-produto img",
    ".gallery img",
    ".swiper img",
    ".slick-slide img",
    "[data-fancybox] img",
    "[data-zoom-image]",
    "[data-large_image]",
    "[class*=product] img",
    "[class*=produto] img",
    "[class*=gallery] img",
    "[class*=galeria] img",
    "[id*=product] img",
    "[id*=produto] img",
    "[itemprop=image]",
]


def _extrair_imagens_por_selectors(soup: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []

    for selector in PRODUCT_IMAGE_SELECTORS:
        try:
            elementos = soup.select(selector)
        except Exception:
            elementos = []

        for el in elementos:
            candidatos = [
                el.get("src"),
                el.get("data-src"),
                el.get("data-original"),
                el.get("data-lazy"),
                el.get("data-zoom-image"),
                el.get("data-large_image"),
                el.get("href"),
                el.get("srcset"),
            ]

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=selector,
                    min_score=4,
                )

    return urls


def _coletar_imagens_produto(
    soup: BeautifulSoup,
    base_url: str,
    jsonld: dict[str, Any],
) -> list[str]:
    urls: list[str] = []

    imagens_json = jsonld.get("image")
    if isinstance(imagens_json, str):
        imagens_json = [imagens_json]

    if isinstance(imagens_json, list):
        for item in imagens_json:
            _adicionar_url_imagem(
                urls=urls,
                url=_safe_str(item),
                base_url=base_url,
                contexto="json-ld",
                min_score=1,
            )

    for meta_name in ("og:image", "twitter:image"):
        meta_url = meta_content_crawler(soup, "property", meta_name) or meta_content_crawler(
            soup, "name", meta_name
        )
        _adicionar_url_imagem(
            urls=urls,
            url=meta_url,
            base_url=base_url,
            contexto=meta_name,
            min_score=2,
        )

    for url in _extrair_imagens_por_selectors(soup, base_url):
        if url not in urls:
            urls.append(url)

    if len(urls) < 2:
        todas = _safe_str(todas_imagens_crawler(soup, base_url))
        for item in [p.strip() for p in todas.split("|") if p.strip()]:
            _adicionar_url_imagem(
                urls=urls,
                url=item,
                base_url=base_url,
                contexto="helper_fallback",
                min_score=5,
            )

    if len(urls) < 2:
        for img in soup.find_all("img"):
            candidatos = [
                img.get("src"),
                img.get("data-src"),
                img.get("data-original"),
                img.get("data-lazy"),
                img.get("data-zoom-image"),
                img.get("data-large_image"),
                img.get("srcset"),
            ]

            classes = " ".join(img.get("class", []) or [])
            alt = _safe_str(img.get("alt"))
            parent_class = ""

            try:
                parent = img.parent
                if parent:
                    parent_class = " ".join(parent.get("class", []) or [])
            except Exception:
                parent_class = ""

            contexto = " ".join([classes, alt, parent_class]).strip()

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=contexto,
                    min_score=6,
                )

    return urls[:8]


def extrair_imagens(soup: BeautifulSoup, url: str, jsonld: dict[str, Any]) -> str:
    imagens = _coletar_imagens_produto(soup, url, jsonld or {})
    return _filtrar_imagens(imagens)
