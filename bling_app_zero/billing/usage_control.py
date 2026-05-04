from __future__ import annotations

from datetime import datetime

from bling_app_zero.billing.plans import get_plan
from bling_app_zero.core.tenant import get_workspace_id
from bling_app_zero.enterprise.cloud_client import select_rows


def get_monthly_usage() -> int:
    workspace = get_workspace_id()
    ok, rows = select_rows(
        "usage_logs",
        query=f"workspace=eq.{workspace}",
        limit=1000,
    )
    if not ok or not rows:
        return 0

    now = datetime.utcnow()
    count = 0

    for r in rows:
        try:
            created = datetime.fromisoformat(r.get("created_at", ""))
            if created.month == now.month and created.year == now.year:
                count += 1
        except Exception:
            continue

    return count


def can_use_feature(plan_id: str) -> tuple[bool, str]:
    plan = get_plan(plan_id)
    used = get_monthly_usage()

    if used >= plan.monthly_import_limit:
        return False, f"Limite do plano atingido ({plan.monthly_import_limit}/mês)"

    return True, "OK"
