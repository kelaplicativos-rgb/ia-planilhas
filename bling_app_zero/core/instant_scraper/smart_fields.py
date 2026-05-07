from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class FieldRequest:
    """Representa uma coluna solicitada pela planilha modelo.

    O motor FLASH usa esta estrutura para buscar somente o que a operação atual
    precisa. Isso mantém cadastro e estoque separados e evita captura excessiva.
    """

    original_name: str
    normalized_name: str
    kind: str
    required: bool = False


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "codigo", "código", "cod", "referencia", "referência", "id produto"),
    "gtin": ("gtin", "ean", "codigo de barras", "código de barras", "barcode"),
    "name": ("nome", "produto", "descricao", "descrição", "descricao curta", "descrição curta"),
    "description": ("descricao complementar", "descrição complementar", "descricao completa", "descrição completa"),
    "price": ("preco", "preço", "valor", "valor unitario", "valor unitário", "preco unitario", "preço unitário"),
    "stock": ("estoque", "quantidade", "saldo", "balanco", "balanço", "qtd"),
    "image": ("imagem", "imagens", "url imagem", "url imagens", "foto", "fotos"),
    "brand": ("marca", "fabricante"),
    "category": ("categoria", "departamento", "grupo"),
    "ncm": ("ncm",),
    "deposit": ("deposito", "depósito", "almoxarifado"),
    "supplier": ("fornecedor",),
}

_REQUIRED_HINTS = ("obrig", "required", "necess")


def normalize_column_name(value: object) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ü": "u",
        "ç": "c",
        "º": "o",
        "ª": "a",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = " ".join(text.replace("_", " ").replace("-", " ").split())
    return text


def classify_field(column_name: object) -> str:
    normalized = normalize_column_name(column_name)
    for kind, aliases in _FIELD_ALIASES.items():
        normalized_aliases = [normalize_column_name(alias) for alias in aliases]
        if normalized in normalized_aliases:
            return kind
        if any(alias in normalized for alias in normalized_aliases if len(alias) >= 3):
            return kind
    return "custom"


def is_required_field(column_name: object) -> bool:
    normalized = normalize_column_name(column_name)
    return any(hint in normalized for hint in _REQUIRED_HINTS)


def build_field_requests(model_columns: Iterable[object] | pd.DataFrame | None) -> list[FieldRequest]:
    """Cria a lista de campos que o motor deve tentar preencher.

    Aceita tanto uma lista de colunas quanto um DataFrame de modelo do Bling.
    """

    if model_columns is None:
        return []

    if isinstance(model_columns, pd.DataFrame):
        columns = list(model_columns.columns)
    else:
        columns = list(model_columns)

    requests: list[FieldRequest] = []
    seen: set[str] = set()
    for column in columns:
        original = str(column or "").strip()
        if not original:
            continue
        normalized = normalize_column_name(original)
        if normalized in seen:
            continue
        seen.add(normalized)
        requests.append(
            FieldRequest(
                original_name=original,
                normalized_name=normalized,
                kind=classify_field(original),
                required=is_required_field(original),
            )
        )
    return requests


def requested_kinds(field_requests: Iterable[FieldRequest]) -> set[str]:
    return {field.kind for field in field_requests if field.kind and field.kind != "custom"}
