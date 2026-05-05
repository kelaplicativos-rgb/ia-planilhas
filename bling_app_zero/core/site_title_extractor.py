from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fallback_title_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    bits = [b for b in parsed.path.split("/") if b.strip()]
    candidate = bits[-1] if bits else parsed.netloc
    candidate = re.sub(r"[-_]+", " ", candidate).strip()
    return candidate.title() if candidate else f"Produto capturado do site {index}"


def title_from_html(page_html: str) -> str:
    patterns = [
        r"<meta[^>]+property=['\"]og:title['\"][^>]+content=['\"]([^'\"]+)['\"]",
        r"<meta[^>]+content=['\"]([^'\"]+)['\"][^>]+property=['\"]og:title['\"]",
        r"<h1[^>]*>(.*?)</h1>",
        r"<title[^>]*>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html or "", flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        title = re.sub(r"<[^>]+>", " ", match.group(1))
        title = clean_text(title)
        if title:
            return title
    return ""


def extract_product_title(url: str, index: int) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.ok:
            title = title_from_html(response.text)
            if title:
                return title
    except Exception:
        pass

    return fallback_title_from_url(url, index)
