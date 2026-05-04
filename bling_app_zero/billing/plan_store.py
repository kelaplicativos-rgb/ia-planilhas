from __future__ import annotations

from typing import Any

from bling_app_zero.core.tenant import get_workspace_id
from bling_app_zero.enterprise.cloud_client import insert_row, select_rows
from bling_app_zero.core.saas_store import read_json, write_json


def get_current_plan(workspace: str | None = None) -> str:
    ws = workspace or get_workspace_id()

    ok, rows = select_rows("subscriptions", query=f"workspace=eq.{ws}", limit=1)
    if ok and rows:
        plan = rows[0].get("plan_id")
        if plan:
            return str(plan)

    local = read_json("subscription.json", {}, ws)
    if isinstance(local, dict) and local.get("plan_id"):
        return str(local["plan_id"])

    return "free"


def set_current_plan(plan_id: str, workspace: str | None = None, source: str = "manual") -> bool:
    ws = workspace or get_workspace_id()
    payload: dict[str, Any] = {
        "workspace": ws,
        "plan_id": plan_id,
        "status": "active",
        "source": source,
    }

    ok, _ = insert_row("subscriptions", payload)
    write_json("subscription.json", payload, ws)
    return bool(ok)
