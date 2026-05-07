from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.parse import urlparse

import requests

from ..schema import FieldIntent, RequestedField


@dataclass
class SiteSnapshot:
    url: str
    html: str = ""
    text: str = ""
    ok: bool = False
    error: str = ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def fetch_url(url: str, timeout: int = 20) -> SiteSnapshot:
    safe_url = str(url or "").strip()
    if not safe_url:
        return SiteSnapshot(url="", error="URL vazia")
    if not safe_url.startswith(("http://", "https://")):
        safe_url = "https://" + safe_url
    try:
        response = requests.get(safe_url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        html = response.text or ""
        text = html_to_text(html)
        return SiteSnapshot(url=safe_url, html=html, text=text, ok=True)
    except Exception as exc:
        return SiteSnapshot(url=safe_url, error=str(exc))


def html_to_text(html: str) -> str:
    clean = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    clean = re.sub(r"<style[\s\S]*?</style>", " ", clean, flags=re.I)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def extract_title(snapshot: SiteSnapshot) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
        r'<h1[^>]*>(.*?)</h1>',
    ]
    for pattern in patterns:
        match = re.search(pattern, snapshot.html, flags=re.I | re.S)
        if match:
            return html_to_text(match.group(1))[:250]
    path = urlparse(snapshot.url).path.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").strip().title()


def extract_price(snapshot: SiteSnapshot) -> str:
    html = snapshot.html
    meta_patterns = [
        r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']product:price:amount["\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, html, flags=re.I)
        if match:
            return normalize_price(match.group(1))
    text = snapshot.text
    match = re.search(r"R\$\s*([0-9\.]+,[0-9]{2})", text)
    if match:
        return normalize_price(match.group(1))
    return ""


def normalize_price(value: object) -> str:
    text = str(value or "").strip()
    match = re.search(r"[0-9][0-9\.,]*", text)
    if not match:
        return ""
    raw = match.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return f"{float(raw):.2f}".replace(".", ",")
    except Exception:
        return ""


def extract_images(snapshot: SiteSnapshot, limit: int = 12) -> str:
    candidates = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', snapshot.html, flags=re.I)
    candidates += re.findall(r'<img[^>]+src=["\']([^"\']+)', snapshot.html, flags=re.I)
    cleaned: list[str] = []
    for src in candidates:
        src = unescape(src).strip()
        low = src.lower()
        if not src or any(bad in low for bad in ("logo", "sprite", "placeholder", "icon", "tracking")):
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            parsed = urlparse(snapshot.url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"
        if src not in cleaned:
            cleaned.append(src)
        if len(cleaned) >= limit:
            break
    return "|".join(cleaned)


def extract_gtin(snapshot: SiteSnapshot) -> str:
    text = snapshot.text
    for pattern in (r"(?:GTIN|EAN|Código de barras|Codigo de barras)\s*[:\-]?\s*(\d{8,14})", r"\b(\d{13})\b"):
        match = re.search(pattern, text, flags=re.I)
        if match:
            digits = re.sub(r"\D+", "", match.group(1))
            if len(digits) in {8, 12, 13, 14}:
                return digits
    return ""


def extract_stock(snapshot: SiteSnapshot) -> str:
    text = snapshot.text.lower()
    if any(token in text for token in ("sem estoque", "indisponivel", "indisponível", "esgotado", "zerado")):
        return "0"
    match = re.search(r"(?:estoque|quantidade|saldo)\D{0,20}(\d{1,6})", text, flags=re.I)
    if match:
        return match.group(1)
    return ""


def should_extract(intent: FieldIntent, schema: Iterable[RequestedField]) -> bool:
    return any(field.intent == intent for field in schema)
