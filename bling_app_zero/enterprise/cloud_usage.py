from __future__ import annotations

from datetime import datetime, timezone

from bling_app_zero.core.tenant import get_workspace_id
from bling_app_zero.enterprise.cloud_client import insert_row


def log_usage(event: str, payload: dict | None = None) -> None:
    workspace = get_workspace_id()

    data = {
        "workspace": workspace,
        "event": event,
        "payload": payload or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    ok, _ = insert_row("usage_logs", data)
    if not ok:
        return
