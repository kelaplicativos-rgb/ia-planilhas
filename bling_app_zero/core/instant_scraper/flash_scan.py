from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .smart_fields import FieldRequest, requested_kinds


@dataclass
class FlashScanOutput:
    url: str
    html: str = ""
    status_code: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    used_deep: bool = False


class FlashScanExtractor:
    """Motor rápido para páginas estáticas.

    Ele só procura os tipos de campos solicitados pela planilha modelo.
    """

    def __init__(self, timeout: int = 18) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
            }
        )

    def fetch(self, url: str) -> FlashScanOutput:
        output = FlashScanOutput(url=url)
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            output.status_code = response.status_code
            response.raise_for_status()
            output.html = response.text or ""
        except Exception as exc:  # pragma: no cover - proteção para Streamlit Cloud
            output.errors.append(f"Falha no FLASH SCAN: {exc}")
        return output

    def extract(self, url: str, field_requests: list[FieldRequest]) -> FlashScanOutput:
        output = self.fetch(url)
        if not output.html:
            return output

        kinds = requested_kinds(field_requests)
        soup = BeautifulSoup(output.html, "html.parser")
        text = _clean_text(soup.get_text(" "))
        jsonld_items = _extract_jsonld(soup)

        if "name" in kinds:
            output.data["name"] = _first_non_empty(
                _jsonld_value(jsonld_items, ("name",)),
                _meta_content(soup, ["og:title", "twitter:title", "title"]),
                soup.title.string if soup.title else "",
            )

        if "description" in kinds:
            output.data["description"] = _first_non_empty(
                _jsonld_value(jsonld_items, ("description",)),
                _meta_content(soup, ["description", "og:description", "twitter:description"]),
            )

        if "price" in kinds:
            output.data["price"] = _first_non_empty(
                _jsonld_offer_value(jsonld_items, "price"),
                _meta_content(soup, ["product:price:amount", "og:price:amount"]),
                _regex_price(text),
            )

        if "stock" in kinds:
            output.data["stock"] = _extract_stock(text)

        if "sku" in kinds:
            output.data["sku"] = _first_non_empty(
                _jsonld_value(jsonld_items, ("sku", "mpn")),
                _regex_value(text, r"(?:sku|c[oó]d\.?|refer[eê]ncia|ref\.?)[\s:#-]*([A-Za-z0-9._/-]{2,60})"),
            )

        if "gtin" in kinds:
            output.data["gtin"] = _first_non_empty(
                _jsonld_value(jsonld_items, ("gtin", "gtin8", "gtin12", "gtin13", "gtin14", "ean")),
                _regex_value(text, r"(?:gtin|ean|c[oó]digo de barras)[\s:#-]*(\d{8,14})"),
            )

        if "image" in kinds:
            output.data["image"] = "|".join(_extract_images(soup, url, jsonld_items))

        if "brand" in kinds:
            output.data["brand"] = _first_non_empty(
                _jsonld_brand(jsonld_items),
                _regex_value(text, r"(?:marca|fabricante)[\s:#-]*([A-Za-z0-9À-ÿ ._-]{2,60})"),
            )

        if "category" in kinds:
            output.data["category"] = _first_non_empty(
                _jsonld_value(jsonld_items, ("category",)),
                _breadcrumb_text(soup),
            )

        if "ncm" in kinds:
            output.data["ncm"] = _regex_value(text, r"(?:ncm)[\s:#-]*(\d{8})")

        return output


def _clean_text(value: object) -> str:
    return " ".join(unescape(str(value or "")).replace("\xa0", " ").split())


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _extract_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ")
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if isinstance(parsed, list):
            items.extend([item for item in parsed if isinstance(item, dict)])
        elif isinstance(parsed, dict):
            graph = parsed.get("@graph")
            if isinstance(graph, list):
                items.extend([item for item in graph if isinstance(item, dict)])
            items.append(parsed)
    return items


def _jsonld_value(items: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    for item in items:
        for key in keys:
            value = item.get(key)
            if isinstance(value, (str, int, float)):
                return str(value)
    return ""


def _jsonld_offer_value(items: list[dict[str, Any]], key: str) -> str:
    for item in items:
        offers = item.get("offers")
        if isinstance(offers, dict):
            value = offers.get(key)
            if value is not None:
                return str(value)
        if isinstance(offers, list):
            for offer in offers:
                if isinstance(offer, dict) and offer.get(key) is not None:
                    return str(offer.get(key))
    return ""


def _jsonld_brand(items: list[dict[str, Any]]) -> str:
    for item in items:
        brand = item.get("brand")
        if isinstance(brand, dict):
            return _clean_text(brand.get("name"))
        if isinstance(brand, str):
            return brand
    return ""


def _meta_content(soup: BeautifulSoup, names: list[str]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return str(tag.get("content"))
    return ""


def _regex_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ""


def _regex_price(text: str) -> str:
    match = re.search(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})", text)
    return match.group(1) if match else ""


def _extract_stock(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("sem estoque", "indisponível", "indisponivel", "esgotado", "produto indispon")):
        return "0"
    qtd = _regex_value(text, r"(?:estoque|dispon[ií]vel|saldo|quantidade)[\s:#-]*(\d{1,6})")
    if qtd:
        return qtd
    if any(term in lowered for term in ("comprar", "adicionar ao carrinho", "em estoque", "disponível", "disponivel")):
        return "1"
    return ""


def _extract_images(soup: BeautifulSoup, url: str, jsonld_items: list[dict[str, Any]]) -> list[str]:
    images: list[str] = []
    for item in jsonld_items:
        value = item.get("image")
        if isinstance(value, str):
            images.append(value)
        elif isinstance(value, list):
            images.extend([str(v) for v in value if v])

    for tag in soup.find_all(["img", "source"]):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-original") or tag.get("srcset")
        if not src:
            continue
        src_text = str(src).split(",")[0].split()[0]
        images.append(urljoin(url, src_text))

    cleaned: list[str] = []
    seen: set[str] = set()
    bad_terms = ("logo", "sprite", "placeholder", "blank", "loading", "icon", "favicon")
    for image in images:
        image = image.strip()
        if not image or image in seen:
            continue
        if any(term in image.lower() for term in bad_terms):
            continue
        seen.add(image)
        cleaned.append(image)
        if len(cleaned) >= 12:
            break
    return cleaned


def _breadcrumb_text(soup: BeautifulSoup) -> str:
    selectors = ["[itemtype*='BreadcrumbList']", ".breadcrumb", ".breadcrumbs", "nav[aria-label*='breadcrumb']"]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            parts = [_clean_text(part) for part in node.stripped_strings]
            parts = [part for part in parts if part]
            if parts:
                return " > ".join(parts)
    return ""
