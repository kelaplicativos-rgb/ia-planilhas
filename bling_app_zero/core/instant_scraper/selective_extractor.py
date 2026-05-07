from __future__ import annotations

from typing import Any

from .smart_fields import FieldRequest


def align_extracted_data_to_model(
    extracted: dict[str, Any],
    field_requests: list[FieldRequest],
    *,
    include_support_name: bool = True,
) -> dict[str, Any]:
    """Converte dados extraídos para as colunas exatas da planilha modelo.

    Regra central do BLINGFLASH:
    - se a coluna foi solicitada no modelo, tenta preencher;
    - se não encontrou, deixa vazio;
    - não inventa colunas extras, exceto nome de apoio quando permitido.
    """

    row: dict[str, Any] = {}
    for field in field_requests:
        value = extracted.get(field.kind, "")
        row[field.original_name] = value if value is not None else ""

    if include_support_name and "Nome apoio" not in row and extracted.get("name"):
        row["Nome apoio"] = extracted.get("name", "")

    return row


def operation_defaults(operation: str) -> dict[str, Any]:
    normalized = (operation or "").strip().lower()
    if "estoque" in normalized:
        return {
            "mode": "estoque",
            "include_support_name": True,
            "search_only_requested_fields": True,
        }
    return {
        "mode": "cadastro",
        "include_support_name": False,
        "search_only_requested_fields": True,
    }
