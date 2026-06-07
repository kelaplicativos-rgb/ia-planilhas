from __future__ import annotations

from bling_app_zero.core.verified_api_sender import send_verified_products as _original_send_verified_products
from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults
from bling_app_zero.core.blingfix_verified_runtime_patch import apply_blingfix_to_verified_module as _apply_payload_guard

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_api_sender_guarded.py'


def send_verified_products(df, *, limit=None, progress_callback=None):
    from bling_app_zero.core import verified_api_sender

    _apply_payload_guard(verified_api_sender)
    fixed_df = apply_dataframe_send_defaults(df)
    return _original_send_verified_products(fixed_df, limit=limit, progress_callback=progress_callback)


__all__ = ['RESPONSIBLE_FILE', 'send_verified_products']
