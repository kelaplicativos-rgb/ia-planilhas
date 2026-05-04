from __future__ import annotations

from bling_app_zero.billing.plan_store import set_current_plan


def process_event(data: dict) -> bool:
    try:
        workspace = data.get("workspace")
        plan = data.get("plan_id")

        if not workspace or not plan:
            return False

        return set_current_plan(plan, workspace, source="webhook")

    except Exception:
        return False
