from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class PaymentConfig:
    provider: str
    stripe_checkout_url: str
    mercado_pago_checkout_url: str
    webhook_secret: str


def _secret(path: str, default: str = "") -> str:
    try:
        node = st.secrets
        for part in path.split("."):
            node = node[part]
        return str(node)
    except Exception:
        return default


def get_payment_config() -> PaymentConfig:
    return PaymentConfig(
        provider=_secret("payments.provider", os.getenv("PAYMENTS_PROVIDER", "manual")),
        stripe_checkout_url=_secret("payments.stripe_checkout_url", os.getenv("STRIPE_CHECKOUT_URL", "")),
        mercado_pago_checkout_url=_secret("payments.mercado_pago_checkout_url", os.getenv("MERCADO_PAGO_CHECKOUT_URL", "")),
        webhook_secret=_secret("payments.webhook_secret", os.getenv("PAYMENTS_WEBHOOK_SECRET", "")),
    )
