from __future__ import annotations

"""Motor especialista em descobrir valor real de estoque em páginas de produto.

Este módulo é independente do crawler de estoque. Ele recebe HTML/BeautifulSoup
já carregado e procura quantidade real em todas as fontes úteis da página:
JSON-LD, metatags, atributos HTML, scripts internos, texto visível e sinais de
indisponibilidade/disponibilidade.

Regra:
- se achar termo claro de indisponível, retorna 0;
- se achar quantidade real, retorna essa quantidade;
- se só houver sinal de disponível sem número, retorna 1;
- se nada for encontrado, retorna vazio.
"""

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Iterable

from bs4 import BeautifulSoup

OUT_OF_STOCK_TERMS = (
    "sem estoque",
    "indisponivel",
    "indisponível",
    "esgotado",
    "fora de estoque",
    "produto indisponivel",
    "produto indisponível",
    "avise-me",
    "aviseme",
    "sob consulta",
)
IN_STOCK_TERMS = (
    "em estoque",
    "disponivel",
    "disponível",
    "comprar",
    "adicionar ao carrinho",
    "produto disponivel",
    "produto disponível",
    "pronta entrega",
)
REAL_STOCK_PATTERNS = (
    re.compile(r"(?:estoque|saldo|quantidade|qtd)\s*(?:dispon[ií]vel)?\s*[:#\-]?\s*(\d+(?:[\.,]\d+)?)", re.I),
    re.compile(r"(\d+(?:[\.,]\d+)?)\s*(?:unidades|unidade|itens|item|pe[cç]as|pe[cç]a)\s*(?:em estoque|dispon[ií]veis|dispon[ií]vel)", re.I),
    re.compile(r"(?:restam|apenas|somente)\s*(\d+(?:[\.,]\d+)?)\s*(?:unidades|unidade|itens|item|pe[cç]as|pe[cç]a)?", re.I),
    re.compile(r"(?:stock|inventory|available_quantity|quantity_available|stock_quantity|qty|quantity|availableQuantity)\s*[=:]\s*[\"']?(\d+(?:[\.,]\d+)?)", re.I),
)
STOCK_ATTR_NAMES = (
    "data-stock",
    "data-estoque",
    "data-quantity",
    "data-qty",
    "data-saldo",
    "data-available-quantity",
    "data-stock-quantity",
    "stock",
    "quantity",
    "qty",
)
JSON_STOCK_KEYS = (
    "inventoryLevel",
    "stockLevel",
    "stockQuantity",
    "quantity",
    "qty",
    "availableQuantity",
    "available_quantity",
    "quantityAvailable",
    "availabilityCount",
    "stock",
    "inventory",
)


@dataclass(frozen=True)
class StockValueResult:
    quantity: str
    source: str
    confidence: str
    reason: str = ""

    @property
    def found(self) -> bool:
        return bool(str(self.quantity or "").strip())


def clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_quantity(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"\d+(?:[\.,]\d+)?", text)
    if not match:
        return ""
    number = match.group(0).replace(",", ".")
    try:
        numeric = float(number)
    except Exception:
        return ""
    if numeric < 0:
        return ""
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric).rstrip("0").rstrip(".")


def _iter_json_payloads(soup: BeautifulSoup) -> Iterable[Any]:
    for script in soup.find_all("script"):
        script_type = str(script.get("type") or "").lower()
        text = script.string or script.get_text(" ", strip=True) or ""
        if not text:
            continue
        if "json" not in script_type and not text.lstrip().startswith(("{", "[")):
            continue
        try:
            yield json.loads(text)
        except Exception:
            continue


def _iter_dicts(payload: Any) -> Iterable[dict[str, Any]]:
    stack = [payload]
    while stack:
        item = stack.pop(0)
        if isinstance(item, dict):
            yield item
            for value in item.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)


def _quantity_from_dict(obj: dict[str, Any]) -> str:
    for key in JSON_STOCK_KEYS:
        if key not in obj:
            continue
        value = obj.get(key)
        if isinstance(value, dict):
            nested = _quantity_from_any(value)
            if nested:
                return nested
        if isinstance(value, list):
            nested = _quantity_from_any(value)
            if nested:
                return nested
        qty = normalize_quantity(value)
        if qty:
            return qty

    additional = obj.get("additionalProperty") or obj.get("additionalProperties")
    if isinstance(additional, list):
        for item in additional:
            if not isinstance(item, dict):
                continue
            name = clean_text(item.get("name") or item.get("propertyID") or item.get("@type")).lower()
            if any(term in name for term in ("estoque", "saldo", "quantidade", "stock", "inventory", "quantity")):
                qty = normalize_quantity(item.get("value"))
                if qty:
                    return qty
    return ""


def _quantity_from_any(value: Any) -> str:
    if isinstance(value, dict):
        return _quantity_from_dict(value)
    if isinstance(value, list):
        for item in value:
            qty = _quantity_from_any(item)
            if qty:
                return qty
    return normalize_quantity(value)


def _quantity_from_json(soup: BeautifulSoup) -> str:
    for payload in _iter_json_payloads(soup):
        for obj in _iter_dicts(payload):
            qty = _quantity_from_dict(obj)
            if qty:
                return qty
    return ""


def _quantity_from_meta(soup: BeautifulSoup) -> str:
    for name in ("inventoryLevel", "stockLevel", "stock", "quantity", "availableQuantity", "qty"):
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name}) or soup.find(attrs={"itemprop": name})
        if not tag:
            continue
        qty = normalize_quantity(tag.get("content") or tag.get("value") or tag.get_text(" ", strip=True))
        if qty:
            return qty
    return ""


def _quantity_from_attrs(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(True):
        attrs = getattr(tag, "attrs", {}) or {}
        for name in STOCK_ATTR_NAMES:
            if name in attrs:
                qty = normalize_quantity(attrs.get(name))
                if qty:
                    return qty
    return ""


def _quantity_from_scripts(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script"):
        text = script.string or script.get_text(" ", strip=True) or ""
        if not text:
            continue
        for pattern in REAL_STOCK_PATTERNS:
            match = pattern.search(text)
            if match:
                qty = normalize_quantity(match.group(1))
                if qty:
                    return qty
    return ""


def _quantity_from_text(text: str) -> str:
    for pattern in REAL_STOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            qty = normalize_quantity(match.group(1))
            if qty:
                return qty
    return ""


def extract_real_stock_value(html: str, *, page_url: str = "") -> StockValueResult:
    soup = BeautifulSoup(html or "", "html.parser")
    full_text = soup.get_text(" ", strip=True)
    lower = full_text.lower()

    if any(term in lower for term in OUT_OF_STOCK_TERMS):
        return StockValueResult("0", "texto_indisponivel", "alta", "termo de indisponibilidade encontrado")

    sources = (
        ("json", _quantity_from_json),
        ("meta_itemprop", _quantity_from_meta),
        ("html_attrs", _quantity_from_attrs),
        ("scripts", _quantity_from_scripts),
        ("texto", lambda s: _quantity_from_text(full_text)),
    )
    for source, extractor in sources:
        qty = extractor(soup)
        if qty:
            return StockValueResult(qty, source, "alta", f"quantidade extraída de {source}")

    if any(term in lower for term in IN_STOCK_TERMS):
        return StockValueResult("1", "fallback_disponivel_sem_quantidade", "baixa", "disponível, mas sem quantidade real exposta")

    return StockValueResult("", "nao_encontrado", "nenhuma", "nenhum estoque detectado")


__all__ = ["StockValueResult", "extract_real_stock_value", "normalize_quantity"]
