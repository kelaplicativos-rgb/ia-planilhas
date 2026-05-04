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


def is_numeric_stock(value: Any) -> bool:
    text = clean_text(value)
    return bool(re.fullmatch(r"\d{1,9}", text))


def parse_stock_text(text: Any, *, positive_default: int | None = None) -> tuple[str, str]:
    """Extrai estoque apenas quando houver quantidade real ou zero explícito.

    Regra principal do estoque inteligente:
    - termo de indisponibilidade/zerado pode retornar 0;
    - quantidade numérica explícita pode retornar a quantidade real;
    - sinal positivo sem quantidade real nunca inventa saldo.

    Assim o detector não troca um saldo verdadeiro por 1 apenas porque encontrou
    textos como "em estoque", "comprar" ou "disponível".
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
    """Lê JSON-LD sem inventar quantidade para disponibilidade positiva."""
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

    if inventory not in (None, ""):
        match = re.search(r"\d+", str(inventory))
        if match:
            return str(max(int(match.group(0)), 0)), "jsonld_inventory_real"

    if any(term in availability for term in ["instock", "in stock", "available"]):
        return "", "jsonld_available_sem_quantidade"

    return "", "jsonld_sem_estoque"


def enrich_dataframe_stock(df: pd.DataFrame) -> pd.DataFrame:
    """Enriquece estoque preservando saldo verdadeiro já existente.

    O enriquecimento só escreve nas colunas de estoque quando:
    - o item estiver claramente zerado/indisponível; ou
    - o texto informar uma quantidade real explícita e não houver saldo real prévio.
    """
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
        saldo_existente = quantidade_real if is_numeric_stock(quantidade_real) else atual
        tem_saldo_real = is_numeric_stock(saldo_existente)

        if tem_saldo_real and not quantidade_real:
            base.at[idx, "quantidade_real"] = saldo_existente
            base.at[idx, "estoque_origem"] = base.at[idx, "estoque_origem"] or "coluna_estoque"

        texto = " | ".join(clean_text(v) for v in row.tolist())
        qtd, origem = parse_stock_text(texto, positive_default=None)

        if qtd == "0" and origem == "termo_zero":
            base.at[idx, "estoque"] = "0"
            base.at[idx, "quantidade_real"] = "0"
            base.at[idx, "estoque_origem"] = origem
            continue

        if qtd != "" and origem == "quantidade_real_texto" and not tem_saldo_real:
            base.at[idx, "estoque"] = qtd
            base.at[idx, "quantidade_real"] = qtd
            base.at[idx, "estoque_origem"] = origem
            continue

        if origem == "positivo_sem_quantidade" and not base.at[idx, "estoque_origem"]:
            base.at[idx, "estoque_origem"] = origem

    return base.fillna("")


def extract_stock_from_html(html: str) -> tuple[str, str]:
    if not html:
        return "", "sem_html"
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "svg"]):
        bad.decompose()
    text = soup.get_text(" ", strip=True)
    return parse_stock_text(text, positive_default=None)
