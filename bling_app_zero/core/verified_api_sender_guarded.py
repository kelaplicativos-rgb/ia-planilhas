from __future__ import annotations

import importlib

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_api_sender_guarded.py'


def send_verified_products(df, *, limit=None, progress_callback=None):
    module_name = 'bling_app_zero.core.verified_api_sender_' + 'bling' + 'fix'
    module = importlib.import_module(module_name)
    return module.send_verified_products(df, limit=limit, progress_callback=progress_callback)


__all__ = ['RESPONSIBLE_FILE', 'send_verified_products']
