from __future__ import annotations

import html
import json
import re
from functools import lru_cache

import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_PRICE_SESSION = requests.Session()
_PRICE_SESSION.headers.update(HEADERS)


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _format_price_br(value: float) -> str:
    return f"{float(value):.2f}".replace(".", ",")


def _parse_price(value: object) -> float | None:
    text = _clean(value)
    if not text:
        return None
    text = text.replace("R$", "").replace(" ", "")
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ",", "."}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        parts = text.split(".")
        if len(parts) > 2:
            text = "".join(parts[:-1]) + "." + parts[-1]
    try:
        number = float(text)
    except Exception:
        return None
    if number <= 0 or number > 1_000_000:
        return None
    return number


def _extract_jsonld_price(page: str) -> float | None:
    for raw in re.findall(r"<script[^>]+type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>", page or "", flags=re.I | re.S):
        try:
            data = json.loads(_clean(raw))
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = _parse_price(offers.get("price") or offers.get("lowPrice") or offers.get("highPrice"))
                if price is not None:
                    return price
            elif isinstance(offers, list):
                stack.extend(offers)
            for key in ("@graph", "hasVariant", "offers"):
                child = item.get(key)
                if isinstance(child, (list, dict)):
                    stack.append(child)
    return None


def extract_price_from_html(page: str) -> str:
    price = _extract_jsonld_price(page)
    if price is not None:
        return _format_price_br(price)

    patterns = [
        r"property=['\"]product:price:amount['\"][^>]+content=['\"]([^'\"]+)['\"]",
        r"content=['\"]([^'\"]+)['\"][^>]+property=['\"]product:price:amount['\"]",
        r"itemprop=['\"]price['\"][^>]+content=['\"]([^'\"]+)['\"]",
        r"content=['\"]([^'\"]+)['\"][^>]+itemprop=['\"]price['\"]",
        r"data-price=['\"]([^'\"]+)['\"]",
        r"preco[^0-9]{0,30}R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
        r"price[^0-9]{0,30}([0-9]+(?:\.[0-9]{2})?)",
        r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
        r"R\$\s*([0-9]+,[0-9]{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, page or "", flags=re.I | re.S)
        if not match:
            continue
        parsed = _parse_price(match.group(1))
        if parsed is not None:
            return _format_price_br(parsed)
    return ""


@lru_cache(maxsize=2048)
def _extract_price_from_url_cached(raw: str) -> str:
    try:
        response = _PRICE_SESSION.get(raw, timeout=4)
        if not response.ok:
            return ""
        return extract_price_from_html(response.text)
    except Exception:
        return ""


def extract_price_from_url(url: object) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    return _extract_price_from_url_cached(raw)
