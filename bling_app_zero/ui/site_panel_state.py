from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_state.py'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
SITE_CAPTURE_STALE_SECONDS = 150
SITE_CAPTURE_HARD_STALE_SECONDS = 900
SITE_CAPTURE_PROGRESS_GRACE_SECONDS = 180
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


def _last_progress_seen_at() -> float:
    try:
        from bling_app_zero.ui.site_progress import last_site_progress_seen_at

        return float(last_site_progress_seen_at() or 0.0)
    except Exception:
        try:
            return float(st.session_state.get('site_progress_last_seen_at') or 0.0)
        except Exception:
            return 0.0


def _progress_has_live_signal(now: float, *, started_at: float, max_age_seconds: int) -> tuple[bool, float, dict]:
    last_seen_at = _last_progress_seen_at()
    last_payload = st.session_state.get('site_progress_last')
    if not isinstance(last_payload, dict):
        last_payload = {}

    last_delta = now - last_seen_at if last_seen_at > 0 else max_age_seconds + 1
    age = now - started_at if started_at > 0 else max_age_seconds + 1
    has_recent_progress = last_seen_at > 0 and last_delta <= SITE_CAPTURE_PROGRESS_GRACE_SECONDS
    has_meaningful_payload = bool(
        last_payload.get('stage')
        or last_payload.get('message')
        or int(float(last_payload.get('urls_found') or last_payload.get('deep_capture_found_products') or 0)) > 0
        or int(float(last_payload.get('processed') or last_payload.get('scanned_pages') or last_payload.get('deep_capture_scanned_pages') or 0)) > 0
    )
    still_inside_hard_limit = age < SITE_CAPTURE_HARD_STALE_SECONDS
    return bool(has_recent_progress and has_meaningful_payload and still_inside_hard_limit), round(last_delta, 2), last_payload


def recover_stale_capture_if_needed(operation: str, *, max_age_seconds: int = SITE_CAPTURE_STALE_SECONDS) -> bool:
    """Destrava captura realmente parada sem matar busca longa ainda viva.

    BLINGFIX: antes a tela limpava qualquer captura com idade maior que 150s,
    mesmo quando o BLINGSMARTSCAN ainda gravava eventos em `site_progress_last`.
    Agora a trava usa batimento vivo: se houve progresso recente, a busca fica
    em andamento e a UI continua mostrando histórico/barra.
    """
    if not bool(st.session_state.get('site_capture_running', False)):
        return False

    try:
        started_at = float(st.session_state.get('site_capture_started_at') or 0.0)
    except Exception:
        started_at = 0.0
    now = time.time()
    age = now - started_at if started_at > 0 else max_age_seconds + 1
    has_result = isinstance(get_site_df(operation), pd.DataFrame)

    if has_result or age < max_age_seconds:
        return False

    has_live_signal, last_progress_age, last_payload = _progress_has_live_signal(now, started_at=started_at, max_age_seconds=max_age_seconds)
    if has_live_signal:
        add_audit_event(
            'site_capture_auto_timeout_postponed_progress_alive',
            area='SITE',
            step='entrada',
            status='INFO',
            details={
                'operation': operation,
                'age_seconds': round(age, 2),
                'max_age_seconds': max_age_seconds,
                'hard_stale_seconds': SITE_CAPTURE_HARD_STALE_SECONDS,
                'last_progress_age_seconds': last_progress_age,
                'last_stage': last_payload.get('stage', ''),
                'last_message': last_payload.get('message', ''),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return False

    clear_site_df(operation, 'captura_travada_auto_timeout_sem_progresso_recente')
    set_capture_state(
        operation=operation,
        running=False,
        finished=False,
        error='A captura anterior ficou sem progresso recente e foi destravada. Execute novamente ou reduza o lote inicial.',
    )
    add_audit_event(
        'site_capture_unstuck_auto_timeout',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={
            'operation': operation,
            'age_seconds': round(age, 2),
            'max_age_seconds': max_age_seconds,
            'hard_stale_seconds': SITE_CAPTURE_HARD_STALE_SECONDS,
            'last_progress_age_seconds': last_progress_age,
            'last_stage': last_payload.get('stage', ''),
            'last_message': last_payload.get('message', ''),
            'reason': 'sem_progresso_recente',
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
