from __future__ import annotations

import streamlit as st

from bling_app_zero.billing.plans import PLANS, get_plan
from bling_app_zero.billing.usage_control import get_monthly_usage
from bling_app_zero.billing.payment_service import start_checkout
from bling_app_zero.billing.plan_store import get_current_plan


def render_billing_panel():
    with st.sidebar.expander("💳 Plano", expanded=False):
        plan_id = get_current_plan()
        plan = get_plan(plan_id)

        st.write(f"Plano atual: {plan.name}")
        st.write(f"Uso mensal: {get_monthly_usage()}/{plan.monthly_import_limit}")

        if st.button("Upgrade"):
            url = start_checkout("pro")
            if url:
                st.success("Abrindo checkout...")
            else:
                st.warning("Configure Stripe ou Mercado Pago")

        with st.expander("Ver planos", expanded=False):
            for p in PLANS.values():
                st.write(f"{p.name} - R$ {p.monthly_price_brl}")
