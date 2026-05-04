from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    monthly_price_brl: float
    monthly_import_limit: int
    features: list[str]


PLANS = {
    "free": Plan(
        id="free",
        name="Free",
        monthly_price_brl=0.0,
        monthly_import_limit=20,
        features=["Até 20 importações/mês", "CSV Bling", "Mapeamento básico"],
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        monthly_price_brl=97.0,
        monthly_import_limit=500,
        features=["Até 500 importações/mês", "Auto aprendizado", "Suporte prioritário"],
    ),
    "business": Plan(
        id="business",
        name="Business",
        monthly_price_brl=197.0,
        monthly_import_limit=2500,
        features=["Até 2500 importações/mês", "Multiusuário", "Cloud/Supabase"],
    ),
}


def get_plan(plan_id: str | None) -> Plan:
    return PLANS.get(str(plan_id or "free").lower(), PLANS["free"])
