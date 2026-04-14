from __future__ import annotations

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers_text import (
    normalizar_url_crawler,
    texto_limpo_crawler,
)


def meta_content_crawler(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    return str(tag.get("content", "")).strip() if tag else ""


def primeiro_texto_crawler(soup: BeautifulSoup, seletores: list[str]) -> str:
    for sel in seletores:
        el = soup.select_one(sel)
        if el:
            txt = texto_limpo_crawler(el.get_text(" ", strip=True))
            if txt:
                return txt
    return ""


def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    imagens: list[str] = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        url = normalizar_url_crawler(base_url, src)
        if not url:
            continue

        if not any(x in url.lower() for x in ["logo", "icon", "placeholder", "thumb"]):
            if url not in imagens:
                imagens.append(url)

    return " | ".join(imagens[:5])
