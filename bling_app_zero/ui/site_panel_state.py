from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_state.py'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
LEGACY_AUTH_KEYS = (
    'guided_login_confirmed_logged_in',
    'guided_login_capture_config',
    'guided_login_capture_prompt',
    'guided_login_capture_last_prepared_at',
    'guided_login_security_resolved',
    'guided_login_products_page_ready',
    'guided_login_capture_mode',
    'guided_login_remote_snapshot_url',
    'guided_login_remote_snapshot_final_url',
    'guided_login_remote_snapshot_title',
    'guided_login_remote_snapshot_ok',
    'guided_login_remote_snapshot_png',
    'guided_login_remote_last_click_nonce',
    'guided_login_remote_desktop_ready',
    'guided_login_remote_desktop_url_ready',
)


def query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def query_urls_default() -> str:
    return query_param('urls') or query_param('url')


def normalize_site_operation_value(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if text in {'estoque', 'estoque_site', 'stock', 'stock_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return UNIVERSAL_OPERATION
    if text in UNIVERSAL_ALIASES:
        return UNIVERSAL_OPERATION
    return ''


def current_site_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final', 'home_slim_flow_operation'):
        normalized = normalize_site_operation_value(st.session_state.get(key))
        if normalized:
            return normalized
    normalized_query = normalize_site_operation_value(query_param('operacao'))
    return normalized_query or UNIVERSAL_OPERATION


def site_df_key(operation: str) -> str:
    return f'df_site_bruto_{operation}'


def store_site_df(operation: str, df_site: pd.DataFrame) -> None:
    st.session_state[site_df_key(operation)] = df_site
    st.session_state['df_site_bruto'] = df_site
    for other in {'cadastro', 'estoque', UNIVERSAL_OPERATION} - {operation}:
        st.session_state.pop(site_df_key(other), None)


def clear_site_df(operation: str, reason: str) -> None:
    removed: list[str] = []
    current_key = site_df_key(operation)
    for key in (current_key, 'df_site_bruto'):
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    add_audit_event(
        'site_capture_stale_source_cleared',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={
            'operation': operation,
            'reason': reason,
            'removed_keys': removed,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def clear_legacy_authenticated_state() -> None:
    removed: list[str] = []
    for key in LEGACY_AUTH_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    for key in list(st.session_state.keys()):
        if str(key).startswith('site_guided_login_enabled_'):
            st.session_state.pop(key, None)
            removed.append(str(key))
    if removed:
        add_audit_event(
            'legacy_authenticated_site_state_cleared',
            area='SITE',
            step='entrada',
            status='OK',
            details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
        )


def get_site_df(operation: str) -> pd.DataFrame | None:
    df_current = st.session_state.get(site_df_key(operation))
    if isinstance(df_current, pd.DataFrame):
        return df_current
    df_legacy = st.session_state.get('df_site_bruto')
    legacy_operation = normalize_site_operation_value(st.session_state.get('operation_site') or st.session_state.get('tipo_operacao_site'))
    if legacy_operation == operation and isinstance(df_legacy, pd.DataFrame):
        return df_legacy
    return None


def has_columns(columns: list[str] | None) -> bool:
    return bool([str(column).strip() for column in (columns or [])])


def has_urls(raw_urls: str) -> bool:
    return bool(str(raw_urls or '').strip())


def orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def set_capture_state(*, operation: str, running: bool, finished: bool, error: str = '', rows: int = 0, columns: int = 0) -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_finished'] = finished
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = operation
    st.session_state['site_capture_result_ready'] = bool(finished and not error and rows > 0)
    st.session_state['site_capture_rows'] = int(rows or 0)
    st.session_state['site_capture_columns'] = int(columns or 0)


def clear_stuck_capture(operation: str) -> None:
    clear_site_df(operation, 'captura_travada_limpa_manualmente')
    set_capture_state(
        operation=operation,
        running=False,
        finished=False,
        error='Captura anterior destravada manualmente. Execute novamente.',
    )
    add_audit_event(
        'site_capture_unstuck_manually',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE},
    )


__all__ = [
    'UNIVERSAL_OPERATION',
    'clear_legacy_authenticated_state',
    'clear_site_df',
    'clear_stuck_capture',
    'current_site_operation',
    'get_site_df',
    'has_columns',
    'has_urls',
    'orange_warning',
    'query_urls_default',
    'set_capture_state',
    'store_site_df',
]
