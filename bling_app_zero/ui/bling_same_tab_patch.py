from __future__ import annotations

from typing import Any

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.bling_same_tab_auth import (
    remember_same_tab_oauth_departure,
    render_same_tab_connect_button,
    render_same_tab_oauth_notice,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_same_tab_patch.py'
_PATCH_FLAG = '_bling_same_tab_auth_patch_installed'


def install_bling_same_tab_auth_patch() -> None:
    """Patch the Bling API entry button to keep OAuth in the same browser tab."""
    try:
        from bling_app_zero.ui import home_bling_api_flow as flow
    except Exception as exc:
        add_audit_event(
            'bling_same_tab_patch_import_failed',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    if getattr(flow, _PATCH_FLAG, False):
        return

    def _patched_render_same_tab_connect_button(auth_url: str) -> None:
        context: dict[str, Any] = {
            'return_to': 'start',
            'source_step': 'bling_connection_entry',
        }
        remember_same_tab_oauth_departure(context)
        render_same_tab_oauth_notice()
        render_same_tab_connect_button(auth_url, 'Conectar ao Bling nesta aba')

    flow.render_same_tab_connect_button = _patched_render_same_tab_connect_button
    setattr(flow, _PATCH_FLAG, True)
    add_audit_event(
        'bling_same_tab_patch_installed',
        area='BLING_OAUTH',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'patched_module': 'bling_app_zero.ui.home_bling_api_flow'},
    )


__all__ = ['install_bling_same_tab_auth_patch']
