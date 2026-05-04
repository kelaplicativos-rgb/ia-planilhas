from __future__ import annotations

from typing import Any

from bling_app_zero.core.tenant import get_workspace_id
from bling_app_zero.enterprise.cloud_client import insert_row, select_rows


def get_mapping(signature: str) -> dict[str, str]:
    workspace = get_workspace_id()
    ok, rows = select_rows(
        "mapping_memory",
        query=f"workspace=eq.{workspace}&signature=eq.{signature}",
        limit=1,
    )
    if not ok or not rows:
        return {}

    item = rows[0]
    mapping = item.get("mapping") or {}
    if isinstance(mapping, dict):
        return {str(k): str(v) for k, v in mapping.items()}
    return {}


def upsert_mapping(signature: str, mapping: dict[str, str], fornecedor_nome: str = "") -> bool:
    workspace = get_workspace_id()

    # tenta inserir primeiro
    payload: dict[str, Any] = {
        "workspace": workspace,
        "signature": signature,
        "fornecedor_nome": fornecedor_nome,
        "mapping": mapping,
    }

    ok, _ = insert_row("mapping_memory", payload)

    # fallback: se já existir, apenas ignora (evita erro de duplicidade)
    return bool(ok)
