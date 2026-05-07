from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd

_EMPTY_VALUES = {"", "nan", "none", "null", "nat"}


def normalize_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_requested_columns(model_df: pd.DataFrame | None) -> list[str]:
    if not isinstance(model_df, pd.DataFrame) or len(model_df.columns) == 0:
        return []
    columns: list[str] = []
    seen: set[str] = set()
    for col in model_df.columns.tolist():
        name = str(col or "").strip()
        if not name:
            continue
        key = normalize_key(name)
        if key in seen:
            continue
        seen.add(key)
        columns.append(name)
    return columns


def is_empty(value: object) -> bool:
    text = str(value or "").strip()
    return normalize_key(text) in _EMPTY_VALUES


def first_existing_value(row: pd.Series, aliases: Iterable[str]) -> str:
    alias_keys = {normalize_key(alias) for alias in aliases if str(alias or "").strip()}
    for col in row.index:
        if normalize_key(col) in alias_keys:
            value = str(row.get(col, "") or "").strip()
            if not is_empty(value):
                return value
    return ""


def detect_operation_from_model(model_df: pd.DataFrame | None, fallback: str = "cadastro") -> str:
    columns = get_requested_columns(model_df)
    text = " | ".join(normalize_key(col) for col in columns)
    score_estoque = 0
    score_cadastro = 0

    for term in ("deposito", "saldo", "balanco", "quantidade", "estoque"):
        if term in text:
            score_estoque += 3
    for term in (
        "descricao",
        "descricao curta",
        "descricao complementar",
        "preco unitario obrigatorio",
        "preco unitario",
        "url imagens externas",
        "imagens",
        "categoria",
        "marca",
        "ncm",
        "peso bruto",
        "peso liquido",
    ):
        if term in text:
            score_cadastro += 2

    if score_estoque > score_cadastro:
        return "estoque"
    if score_cadastro > score_estoque:
        return "cadastro"
    fallback_norm = normalize_key(fallback)
    return "estoque" if "estoque" in fallback_norm else "cadastro"


def operation_label(operation: str) -> str:
    return "Atualização de estoque" if normalize_key(operation) == "estoque" else "Cadastro de produtos"


def build_blank_model_dataframe(model_df: pd.DataFrame | None, rows: int) -> pd.DataFrame:
    columns = get_requested_columns(model_df)
    return pd.DataFrame([{col: "" for col in columns} for _ in range(max(0, int(rows or 0)))])


def keep_only_requested_columns(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or not requested_columns:
        return pd.DataFrame(columns=requested_columns)
    base = df.copy().fillna("")
    output = pd.DataFrame()
    normalized_existing = {normalize_key(col): col for col in base.columns}
    for requested in requested_columns:
        existing = normalized_existing.get(normalize_key(requested))
        if existing is not None:
            output[requested] = base[existing].astype(str).fillna("")
        else:
            output[requested] = ""
    return output.fillna("")
