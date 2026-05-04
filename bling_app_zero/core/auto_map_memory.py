from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bling_app_zero.core.tenant import get_workspace_id


def _memory_path() -> Path:
    workspace = get_workspace_id()
    return Path(".streamlit") / "data" / f"auto_map_memory_{workspace}.json"


def load_memory() -> dict[str, Any]:
    path = _memory_path()
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_memory(memory: dict[str, Any]) -> bool:
    path = _memory_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_supplier_memory(memory: dict[str, Any], signature: str) -> dict[str, str]:
    item = memory.get(signature, {})
    if isinstance(item, dict) and isinstance(item.get("mapping"), dict):
        return {str(k): str(v) for k, v in item["mapping"].items()}
    if isinstance(item, dict):
        return {str(k): str(v) for k, v in item.items() if isinstance(v, str)}
    return {}


def set_supplier_memory(memory: dict[str, Any], signature: str, mapping: dict[str, str], fornecedor_nome: str = "") -> dict[str, Any]:
    memory[signature] = {
        "fornecedor_nome": fornecedor_nome,
        "mapping": {str(k): str(v) for k, v in mapping.items() if str(v).strip()},
    }
    return memory


def delete_supplier_memory(memory: dict[str, Any], signature: str) -> dict[str, Any]:
    memory.pop(signature, None)
    return memory
