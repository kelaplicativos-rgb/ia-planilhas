from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})", re.I)
SKU_RE = re.compile(r"(?:sku|c[oó]d\.?|refer[eê]ncia|ref\.?)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,60})", re.I)
GTIN_RE = re.compile(r"(?:gtin|ean|c[oó]digo de barras)\s*[:#-]?\s*(\d{8,14})", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _first_price(text: str) -> str:
    match = PRICE_RE.search(text or "")
    return match.group(1) if match else ""


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text or "")
    return _clean(match.group(1)) if match else ""


def _image_from_node(node, base_url: str) -> str:
    candidates: list[str] = []
    for tag in node.find_all(["img", "source"]):
        value = tag.get("src") or tag.get("data-src") or tag.get("data-original") or tag.get("srcset")
        if not value:
            continue
        raw = str(value).split(",")[0].split()[0].strip()
        if raw:
            candidates.append(urljoin(base_url, raw))

    bad = ("logo", "sprite", "placeholder", "blank", "loading", "icon", "favicon")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        lowered = item.lower()
        if item in seen or any(term in lowered for term in bad):
            continue
        seen.add(item)
        cleaned.append(item)
        if len(cleaned) >= 12:
            break
    return "|".join(cleaned)


def detect_cards_from_html(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    selectors = [
        "[itemtype*='Product']", "[data-product-id]", "[data-sku]",
        ".product", ".produto", ".product-card", ".produto-card",
        ".card-produto", ".item-produto", ".vitrine li", ".grid li",
        ".products li", ".produtos li", "article",
    ]
    nodes = []
    seen_ids: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            node_id = id(node)
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                nodes.append(node)

    rows: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for node in nodes:
        text = _clean(node.get_text(" "))
        if len(text) < 12:
            continue
        price = _first_price(text)
        link_tag = node.find("a", href=True)
        link = urljoin(base_url, link_tag["href"]) if link_tag else ""
        title = ""
        for selector in ["[itemprop='name']", ".name", ".nome", ".title", ".titulo", "h1", "h2", "h3", "a"]:
            title_node = node.select_one(selector)
            if title_node:
                title = _clean(title_node.get_text(" "))
                if title:
                    break
        if not title:
            compact = text[:120]
            title = compact.split(" R$")[0].strip() if " R$" in compact else compact
        image = _image_from_node(node, base_url)
        if not price and not link and not image:
            continue
        stock = ""
        lowered = text.lower()
        if any(term in lowered for term in ("sem estoque", "indisponível", "indisponivel", "esgotado")):
            stock = "0"
        elif any(term in lowered for term in ("comprar", "em estoque", "disponível", "disponivel")):
            stock = "1"
        row = {
            "name": title,
            "description": text,
            "price": price,
            "stock": stock,
            "sku": _first_match(SKU_RE, text),
            "gtin": _first_match(GTIN_RE, text),
            "image": image,
            "url": link,
        }
        signature = "|".join(str(row.get(k, "")) for k in ("name", "price", "sku", "url"))
        if signature in seen_rows:
            continue
        seen_rows.add(signature)
        rows.append(row)
    return rows
