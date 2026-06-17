from __future__ import annotations

from typing import Any

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_retry_result_runtime_fix.py'
_PATCHED_FLAG = 'bling_retry_result_runtime_fix_installed_v1'


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _is_success_retry_result(payload: Any, identity: str) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get('identity') or '') != str(identity or ''):
        return False
    return _int_value(payload.get('sent')) > 0 and _int_value(payload.get('failed')) == 0 and _int_value(payload.get('skipped')) == 0


def install_bling_retry_result_runtime_fix() -> None:
    try:
        from bling_app_zero.ui import bling_api_batch_panel as panel
    except Exception:
        return

    if getattr(panel, _PATCHED_FLAG, False):
        return

    original_reset_state = getattr(panel, '_reset_state', None)

    def _clear_failed_retry_rows_preserving_success(identity: str) -> None:
        store = st.session_state.get(panel.FAILED_RETRY_ROWS_KEY)
        if isinstance(store, dict) and identity in store:
            store.pop(identity, None)
            st.session_state[panel.FAILED_RETRY_ROWS_KEY] = store

        result_store = st.session_state.get(panel.FAILED_RETRY_RESULT_KEY)
        if _is_success_retry_result(result_store, identity):
            return
        if isinstance(result_store, dict) and result_store.get('identity') == identity:
            st.session_state.pop(panel.FAILED_RETRY_RESULT_KEY, None)

    def _reset_state_clearing_retry_result(identity: str, total: int, operation: str) -> dict[str, Any]:
        st.session_state.pop(panel.FAILED_RETRY_RESULT_KEY, None)
        if callable(original_reset_state):
            return original_reset_state(identity, total, operation)
        return {}

    panel._clear_failed_retry_rows = _clear_failed_retry_rows_preserving_success
    panel._reset_state = _reset_state_clearing_retry_result
    setattr(panel, _PATCHED_FLAG, True)


__all__ = ['install_bling_retry_result_runtime_fix']
