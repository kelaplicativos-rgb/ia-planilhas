from __future__ import annotations

from typing import Any

import pandas as pd

from .selective_extractor import align_extracted_data_to_model, operation_defaults
from .smart_fields import FieldRequest, build_field_requests, normalize_column_name

_KIND_ALIASES = {
    "name": ("name", "nome", "produto", "descrição", "descricao", "title", "titulo"),
    "description": ("description", "descrição completa", "descricao completa", "detalhes"),
    "price": ("price", "preço", "preco", "valor", "r$", "valor unitário", "valor unitario"),
    "stock": ("stock", "estoque", "saldo", "quantidade", "qtd"),
    "sku": ("sku", "codigo", "código", "ref", "referencia", "referência"),
    "gtin": ("gtin", "ean", "barcode", "codigo de barras", "código de barras"),
    "image": ("image", "imagem", "foto", "url imagem"),
    "brand": ("brand", "marca", "fabricante"),
    "category": ("category", "categoria", "departamento", "grupo"),
    "ncm": ("ncm",),
    "url": ("url", "link"),
}


def _find_value(row: dict[str, Any], field: FieldRequest) -> Any:
    if field.kind in row and row.get(field.kind) not in (None, ""):
        return row.get(field.kind)
    normalized_row = {normalize_column_name(key): value for key, value in row.items()}
    aliases = _KIND_ALIASES.get(field.kind, ())
    for alias in aliases:
        key = normalize_column_name(alias)
        if key in normalized_row and normalized_row[key] not in (None, ""):
            return normalized_row[key]
    for key, value in normalized_row.items():
        if value in (None, ""):
            continue
        if field.normalized_name and (field.normalized_name in key or key in field.normalized_name):
            return value
        if any(normalize_column_name(alias) in key for alias in aliases):
            return value
    return ""


def align_rows_to_requested_columns(rows: list[dict[str, Any]], model_columns: list[object] | pd.DataFrame | None, *, operation: str = "cadastro") -> pd.DataFrame:
    field_requests = build_field_requests(model_columns)
    if not field_requests:
        return pd.DataFrame(rows).fillna("")
    defaults = operation_defaults(operation)
    aligned: list[dict[str, Any]] = []
    for source_row in rows:
        extracted_by_kind: dict[str, Any] = {}
        for field in field_requests:
            extracted_by_kind[field.kind] = _find_value(source_row, field)
        aligned.append(
            align_extracted_data_to_model(
                extracted_by_kind,
                field_requests,
                include_support_name=bool(defaults["include_support_name"]),
            )
        )
    return pd.DataFrame(aligned).fillna("")
