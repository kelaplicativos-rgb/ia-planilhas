from __future__ import annotations

import streamlit as st

from bling_app_zero.billing.plans import PLANS, get_plan
from bling_app_zero.billing.usage_control import get_monthly_usage
from bling_app_zero.billing.payment_service import start_checkout
from bling_app_zero.billing.plan_store import get_current_plan


def render_billing_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("💳 Plano")

    plan_id = get_current_plan()
    plan = get_plan(plan_id)

    st.sidebar.write(f"Plano atual: {plan.name}")
    st.sidebar.write(f"Uso mensal: {get_monthly_usage()}/{plan.monthly_import_limit}")

    if st.sidebar.button("Upgrade"):
        url = start_checkout("pro")
        if url:
            st.sidebar.success("Abrindo checkout...")
        else:
            st.sidebar.warning("Configure Stripe ou Mercado Pago")

    with st.sidebar.expander("Ver planos"):
        for p in PLANS.values():
            st.write(f"{p.name} - R$ {p.monthly_price_brl}")
