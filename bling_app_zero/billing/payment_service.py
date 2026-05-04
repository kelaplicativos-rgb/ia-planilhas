from __future__ import annotations

import webbrowser

from bling_app_zero.billing.payment_config import get_payment_config


def start_checkout(plan_id: str) -> str:
    cfg = get_payment_config()

    if cfg.provider == "stripe" and cfg.stripe_checkout_url:
        url = f"{cfg.stripe_checkout_url}?plan={plan_id}"
        webbrowser.open(url)
        return url

    if cfg.provider == "mercado_pago" and cfg.mercado_pago_checkout_url:
        url = f"{cfg.mercado_pago_checkout_url}?plan={plan_id}"
        webbrowser.open(url)
        return url

    return ""
