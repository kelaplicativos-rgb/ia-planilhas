from __future__ import annotations

import re
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


ZERO_TERMS = [
    "sem estoque",
    "sem disponibilidade",
    "indisponivel",
    "indisponível",
    "produto indisponivel",
    "produto indisponível",
    "esgotado",
    "fora de estoque",
    "out of stock",
    "sold out",
    "soldout",
    "zerado",
    "avise-me",
    "avise me",
]

POSITIVE_TERMS = [
    "em estoque",
    "disponivel",
    "disponível",
    "pronta entrega",
    "disponibilidade imediata",
    "in stock",
    "available",
]

STOCK_PATTERNS = [
    r"(?:estoque|saldo|quantidade|dispon[ií]vel|disponibilidade)\s*(?:atual|total|real)?\s*[:\-]?\s*(\d{1,6})",
    r"(?:qtd|qtde|quant\.)\s*[:\-]?\s*(\d{1,6})",
    r"(?:restam|resta)\s*(\d{1,6})",
    r"(\d{1,6})\s*(?:unidades|unidade|itens|item|peças|pecas)\s*(?:em estoque|dispon[ií]ve(?:l|is))",
    r"(?:em estoque)\s*[:\-]?\s*(\d{1,6})",
]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def normalize_text(value: Any) -> str:
    text = clean_text(value).lower()
    table = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    return text.translate(table)


def parse_stock_text(text: Any, *, positive_default: int | None = 1) -> tuple[str, str]:
    """Extrai estoque real quando o texto informa quantidade.

    Retorna (quantidade, origem). Quando há termo zerado, retorna 0.
    Quando só existe sinal positivo, retorna positive_default (normalmente 1),
    indicando estoque positivo sem quantidade real.
    """
    raw = clean_text(text)
    norm = normalize_text(raw)
    if not norm:
        return "", "sem_texto"

    if any(term in norm for term in ZERO_TERMS):
        return "0", "termo_zero"

    for pattern in STOCK_PATTERNS:
        match = re.search(pattern, norm, flags=re.I)
        if match:
            try:
                value = max(int(match.group(1)), 0)
                return str(value), "quantidade_real_texto"
            except Exception:
                continue

    if any(term in norm for term in POSITIVE_TERMS):
        if positive_default is None:
            return "", "positivo_sem_quantidade"
        return str(int(positive_default)), "positivo_sem_quantidade"

    return "", "nao_detectado"


def parse_stock_from_jsonld(product: dict) -> tuple[str, str]:
    if not isinstance(product, dict):
        return "", "sem_jsonld"

    offers = product.get("offers") or {}
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        offers = {}

    availability = normalize_text(offers.get("availability") or product.get("availability") or "")
    inventory = offers.get("inventoryLevel") or offers.get("inventory_level") or offers.get("inventory") or product.get("inventoryLevel")

    if any(term in availability for term in ["outofstock", "soldout", "discontinued"]):
        return "0", "jsonld_availability_zero"
    if any(term in availability for term in ["instock", "in stock", "available"]):
        if inventory not in (None, ""):
            match = re.search(r"\d+", str(inventory))
            if match:
                return str(max(int(match.group(0)), 0)), "jsonld_inventory_real"
        return "1", "jsonld_available_sem_quantidade"

    if inventory not in (None, ""):
        match = re.search(r"\d+", str(inventory))
        if match:
            return str(max(int(match.group(0)), 0)), "jsonld_inventory_real"

    return "", "jsonld_sem_estoque"


def enrich_dataframe_stock(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    if "estoque" not in base.columns:
        base["estoque"] = ""
    if "quantidade_real" not in base.columns:
        base["quantidade_real"] = ""
    if "estoque_origem" not in base.columns:
        base["estoque_origem"] = ""

    for idx, row in base.iterrows():
        atual = clean_text(row.get("estoque", ""))
        quantidade_real = clean_text(row.get("quantidade_real", ""))
        if atual and atual.isdigit() and not quantidade_real:
            base.at[idx, "quantidade_real"] = atual
            base.at[idx, "estoque_origem"] = base.at[idx, "estoque_origem"] or "coluna_estoque"
            continue

        texto = " | ".join(clean_text(v) for v in row.tolist())
        qtd, origem = parse_stock_text(texto)
        if qtd != "":
            base.at[idx, "estoque"] = qtd
            base.at[idx, "quantidade_real"] = qtd
            base.at[idx, "estoque_origem"] = origem

    return base.fillna("")


def extract_stock_from_html(html: str) -> tuple[str, str]:
    if not html:
        return "", "sem_html"
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "svg"]):
        bad.decompose()
    text = soup.get_text(" ", strip=True)
    return parse_stock_text(text)
