from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.alerts import render_alert

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_state.py'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
SITE_CAPTURE_STALE_SECONDS = 90
SITE_CAPTURE_NO_HEARTBEAT_SECONDS = 45
PROGRESS_HEARTBEAT_KEY = 'site_capture_heartbeat_at'
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
    render_alert(str(message or ''), title='Atenção', variant='warning')


def set_capture_state(*, operation: str, running: bool, finished: bool, error: str = '', rows: int = 0, columns: int = 0) -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_finished'] = finished
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = operation
    st.session_state['site_capture_result_ready'] = bool(finished and not error and rows > 0)
    st.session_state['site_capture_rows'] = int(rows or 0)
    st.session_state['site_capture_columns'] = int(columns or 0)
    if running:
        st.session_state[PROGRESS_HEARTBEAT_KEY] = time.time()


def clear_stuck_capture(operation: str) -> None:
    clear_site_df(operation, 'captura_travada_limpa_manualmente')
    st.session_state.pop(PROGRESS_HEARTBEAT_KEY, None)
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


def _seconds_since_state(key: str) -> float:
    try:
        value = float(st.session_state.get(key) or 0.0)
    except Exception:
        value = 0.0
    return time.time() - value if value > 0 else 999999.0


def recover_stale_capture_if_needed(operation: str, *, max_age_seconds: int = SITE_CAPTURE_STALE_SECONDS) -> bool:
    """Destrava captura que ficou marcada como rodando após rerun/interrupção.

    No Streamlit, se a busca por site for interrompida por rerun, refresh ou limite
    de execução, o `finally` do fluxo anterior pode não limpar o estado. Sem esta
    guarda, a tela fica presa em "captura em andamento" sem erro e sem resultado.
    """
    if not bool(st.session_state.get('site_capture_running', False)):
        return False

    try:
        started_at = float(st.session_state.get('site_capture_started_at') or 0.0)
    except Exception:
        started_at = 0.0
    age = time.time() - started_at if started_at > 0 else max_age_seconds + 1
    heartbeat_age = _seconds_since_state(PROGRESS_HEARTBEAT_KEY)
    has_result = isinstance(get_site_df(operation), pd.DataFrame)
    rows = int(st.session_state.get('site_capture_rows') or 0)
    has_progress_log = bool(st.session_state.get('site_progress_log') or [])

    if has_result:
        return False

    stale_by_age = age >= max_age_seconds
    stale_by_heartbeat = heartbeat_age >= SITE_CAPTURE_NO_HEARTBEAT_SECONDS and rows <= 0
    stale_without_log = age >= SITE_CAPTURE_NO_HEARTBEAT_SECONDS and not has_progress_log and rows <= 0

    if not (stale_by_age or stale_by_heartbeat or stale_without_log):
        return False

    clear_site_df(operation, 'captura_travada_auto_timeout')
    st.session_state.pop(PROGRESS_HEARTBEAT_KEY, None)
    set_capture_state(
        operation=operation,
        running=False,
        finished=False,
        error='A captura anterior ficou sem progresso recente ou foi interrompida. Execute novamente com menos links ou use a compatibilidade universal.',
    )
    add_audit_event(
        'site_capture_unstuck_auto_timeout',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={
            'operation': operation,
            'age_seconds': round(age, 2),
            'heartbeat_age_seconds': round(heartbeat_age, 2),
            'max_age_seconds': max_age_seconds,
            'no_heartbeat_seconds': SITE_CAPTURE_NO_HEARTBEAT_SECONDS,
            'has_progress_log': has_progress_log,
            'rows': rows,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


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
    'recover_stale_capture_if_needed',
    'set_capture_state',
    'store_site_df',
]
