from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .link_extractor import looks_like_product_url


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_price(text: str) -> str:
    match = re.search(r"R\$\s*([0-9\.\,]+)", text or "")
    if not match:
        return ""
    return match.group(1).replace(".", "").replace(",", ".")


def extract_images(url: str, soup: BeautifulSoup) -> str:
    images: List[str] = []
    for img in soup.select("img[src], img[data-src]"):
        src = str(img.get("src") or img.get("data-src") or "").strip()
        if not src:
            continue
        img_url = urljoin(url, src)
        low = img_url.lower()
        if any(term in low for term in ["logo", "banner", "sprite", "placeholder", "whatsapp", "icon"]):
            continue
        images.append(img_url)
    return "|".join(list(dict.fromkeys(images))[:10])


def extract_product_from_html(url: str, html: str) -> Optional[Dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    text = clean_text(soup.get_text(" "))

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" "))
    if not title and soup.title:
        title = clean_text(soup.title.get_text(" "))

    price = ""
    meta_price = soup.find("meta", attrs={"property": "product:price:amount"})
    if meta_price and meta_price.get("content"):
        price = clean_text(str(meta_price.get("content", "")))
    if not price:
        price = extract_price(text)

    if not title:
        return None
    if not price and not looks_like_product_url(url):
        return None

    text_lower = text.lower()
    stock = "0" if any(term in text_lower for term in ["sem estoque", "indisponivel", "indisponível", "esgotado"]) else ""

    return {
        "URL": url,
        "Descrição": title,
        "Preço": price,
        "Estoque": stock,
        "Imagens": extract_images(url, soup),
    }
