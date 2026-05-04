from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bling_app_zero.core.tenant import get_workspace_id

BASE_PATH = Path(".streamlit") / "data" / "workspaces"


def workspace_dir(workspace_id: str | None = None) -> Path:
    ws = workspace_id or get_workspace_id()
    path = BASE_PATH / ws
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(name: str, default: Any = None, workspace_id: str | None = None) -> Any:
    path = workspace_dir(workspace_id) / name
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(name: str, data: Any, workspace_id: str | None = None) -> bool:
    path = workspace_dir(workspace_id) / name
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def touch_usage(event: str, payload: dict[str, Any] | None = None, workspace_id: str | None = None) -> None:
    usage = read_json("usage.json", [], workspace_id)
    if not isinstance(usage, list):
        usage = []
    usage.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "payload": payload or {},
    })
    write_json("usage.json", usage[-500:], workspace_id)
