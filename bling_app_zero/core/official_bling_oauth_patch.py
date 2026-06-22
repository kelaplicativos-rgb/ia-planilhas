from __future__ import annotations

from typing import Any, Callable

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core import bling_oauth

RESPONSIBLE_FILE = 'bling_app_zero/core/official_bling_oauth_patch.py'
PATCH_MARKER = '_official_bling_oauth_patch_installed_v1'
FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
CONTEXT_BLING_API = 'bling_api'
FINISH_MODE_API = 'api_direct'
ROUTE_ALLOWED_KEY = 'official_home_flow_route_allowed_v1'
ROUTE_ALLOWED_TARGET_KEY = 'official_home_flow_route_target_v1'

OFFICIAL_RETURN_TARGETS = {
    'mapeiaai_home_bling',
    'official_home_bling',
    'home_bling_api',
}

OFFICIAL_SOURCE_STEPS = {
    'official_home_bling',
    'bling_connection_entry',
    'home_same_tab_connection',
    'home_light_entry',
}


def _looks_like_official_bling_return(payload: dict[str, Any]) -> bool:
    return_to = str(payload.get('return_to') or '').strip()
    source_step = str(payload.get('source_step') or '').strip()
    return return_to in OFFICIAL_RETURN_TARGETS or source_step in OFFICIAL_SOURCE_STEPS


def _restore_official_bling_api_route(payload: dict[str, Any]) -> None:
    store = bling_oauth._state_store()  # type: ignore[attr-defined]
    store[ROUTE_ALLOWED_KEY] = True
    store[ROUTE_ALLOWED_TARGET_KEY] = 'bling_api'
    store['home_active_operation_v2'] = FLOW_WIZARD
    store['home_allow_operation_v2_session'] = True
    store['home_single_page_flow_active'] = True
    store['mapeiaai_home_entry_path'] = 'bling_api'
    store['mapeiaai_flow_kind'] = 'bling_api'
    store['flow_kind'] = 'bling_api'
    store['api_flow_active'] = True
    store['home_bling_connected_same_flow_api_send'] = True
    store['bling_connected_api_flow_active'] = True
    store['home_entry_context'] = CONTEXT_BLING_API
    store['home_slim_entry_context'] = CONTEXT_BLING_API
    store['bling_finish_mode'] = FINISH_MODE_API
    store['finish_mode'] = FINISH_MODE_API
    store['bling_wizard_step'] = STEP_ORIGEM
    store['home_wizard_step'] = STEP_ORIGEM
    store.pop('mapear_planilha_sem_api_active', None)
    store.pop('skip_direct_bling_connection_this_flow', None)

    qp = bling_oauth._query_params_store()  # type: ignore[attr-defined]
    try:
        qp['operation_v2'] = FLOW_WIZARD
        qp['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao', 'operation'):
            qp.pop(key, None)
    except Exception:
        pass

    add_audit_event(
        'official_bling_oauth_return_restored_to_api_core',
        area='BLING_OAUTH',
        status='OK',
        details={
            'return_to': payload.get('return_to') or '',
            'source_step': payload.get('source_step') or '',
            'operation_v2': FLOW_WIZARD,
            'step': STEP_ORIGEM,
            'entry_context': CONTEXT_BLING_API,
            'finish_mode': FINISH_MODE_API,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def install_official_bling_oauth_patch() -> bool:
    if bool(getattr(bling_oauth, PATCH_MARKER, False)):
        return False

    original: Callable[[dict[str, Any]], None] = bling_oauth._restore_oauth_return_context  # type: ignore[attr-defined]

    def patched_restore_oauth_return_context(payload: dict[str, Any]) -> None:
        original(payload)
        if isinstance(payload, dict) and _looks_like_official_bling_return(payload):
            _restore_official_bling_api_route(payload)

    bling_oauth._restore_oauth_return_context = patched_restore_oauth_return_context  # type: ignore[attr-defined]
    setattr(bling_oauth, PATCH_MARKER, True)
    add_audit_event(
        'official_bling_oauth_patch_installed',
        area='BLING_OAUTH',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )
    return True


__all__ = ['install_official_bling_oauth_patch']
