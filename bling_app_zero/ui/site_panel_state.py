from __future__ import annotations

import re
import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_state.py'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
# Captura por site no Streamlit pode ser interrompida pela própria rerenderização.
# O diagnóstico 80 mostrou cadastro/API preso em running por mais de 1 minuto,
# sem erro e sem resultado. O watchdog precisa destravar antes de a tela ficar
# parecendo quebrada para o usuário.
SITE_CAPTURE_STALE_SECONDS = 75
SITE_CAPTURE_HARD_STALE_SECONDS = 420
SITE_CAPTURE_PROGRESS_GRACE_SECONDS = 110
SITE_CAPTURE_MEANINGFUL_IDLE_SECONDS = 180
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
    if text in {'cadastro', 'cadastro_site', 'produto', 'produtos', 'cadastro_produto', 'cadastro_produtos', 'cadastro de produto', 'cadastro de produtos'}:
        return 'cadastro'
    if text in {'estoque', 'estoque_site', 'stock', 'stock_site', 'saldo', 'saldos', 'quantidade', 'quantidades', 'atualizacao_estoque', 'atualização_estoque', 'atualizar_estoque', 'atualizar estoque', 'atualização de estoque', 'atualizacao de estoque'}:
        return 'estoque'
    if text in {'preco', 'preço', 'precos', 'preços', 'price', 'prices', 'atualizacao_preco', 'atualizacao_precos', 'atualização_preço', 'atualização_preços', 'atualização_precos', 'atualizar_preco', 'atualizar_precos', 'atualizar preço', 'atualizar preços', 'atualização de preço', 'atualização de preços', 'atualizacao de preco', 'atualizacao de precos'}:
        return 'atualizacao_preco'
    if text in UNIVERSAL_ALIASES:
        return UNIVERSAL_OPERATION
    return ''


def current_site_operation() -> str:
    for key in (
        'site_capture_operation',
        'blingsmartscan_finished_operation',
        'flow_spine_operation',
        'active_feature_operation',
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
        'home_slim_flow_operation',
    ):
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
    for other in {'cadastro', 'estoque', 'atualizacao_preco', UNIVERSAL_OPERATION} - {operation}:
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
    if operation in {'cadastro', 'estoque', 'atualizacao_preco'} and isinstance(df_legacy, pd.DataFrame):
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


def _last_progress_payload() -> dict:
    for key in ('site_progress_last', 'live_operation_progress_last_v1'):
        payload = st.session_state.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def _extract_int_from_text(text: object, patterns: tuple[str, ...]) -> int:
    raw = str(text or '')
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            try:
                return int(str(match.group(1)).replace('.', '').replace(',', ''))
            except Exception:
                continue
    return 0


def _payload_number(last_payload: dict, *keys: str) -> int:
    for key in keys:
        try:
            value = int(float(last_payload.get(key) or 0))
        except Exception:
            value = 0
        if value > 0:
            return value
    return 0


def _progress_has_live_signal(now: float, *, started_at: float, max_age_seconds: int) -> tuple[bool, float, dict, str]:
    last_seen_at = _last_progress_seen_at()
    last_payload = _last_progress_payload()

    message = str(last_payload.get('message') or '')
    stage = str(last_payload.get('stage') or '')
    found_products = max(
        _payload_number(last_payload, 'urls_found', 'deep_capture_found_products', 'found_products', 'products_found'),
        _extract_int_from_text(message, (r'(\d+)\s*produto', r'(\d+)\s*produto\(s\)', r'produto\(s\).*?(\d+)')),
    )
    scanned_pages = max(
        _payload_number(last_payload, 'processed', 'scanned_pages', 'deep_capture_scanned_pages', 'pages_scanned'),
        _extract_int_from_text(message, (r'(\d+)\s*p[áa]gina', r'(\d+)\s*p[áa]gina\(s\)')),
    )

    last_delta = now - last_seen_at if last_seen_at > 0 else max_age_seconds + 1
    age = now - started_at if started_at > 0 else max_age_seconds + 1
    has_recent_progress = last_seen_at > 0 and last_delta <= SITE_CAPTURE_PROGRESS_GRACE_SECONDS
    has_meaningful_payload = bool(stage or message or found_products > 0 or scanned_pages > 0)
    has_deep_capture_evidence = found_products > 0 or scanned_pages > 0 or 'captura profunda' in stage.lower() or 'captura profunda' in message.lower()
    still_inside_hard_limit = age < SITE_CAPTURE_HARD_STALE_SECONDS
    meaningful_inside_grace = last_seen_at > 0 and last_delta <= SITE_CAPTURE_MEANINGFUL_IDLE_SECONDS and has_deep_capture_evidence

    if has_recent_progress and has_meaningful_payload and still_inside_hard_limit:
        return True, round(last_delta, 2), last_payload, 'progresso_recente'
    if meaningful_inside_grace and still_inside_hard_limit:
        return True, round(last_delta, 2), last_payload, 'captura_profunda_com_evidencia_de_produtos'
    return False, round(last_delta, 2), last_payload, 'sem_sinal_vivo'


def recover_stale_capture_if_needed(operation: str, *, max_age_seconds: int = SITE_CAPTURE_STALE_SECONDS) -> bool:
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

    has_live_signal, last_progress_age, last_payload, live_reason = _progress_has_live_signal(now, started_at=started_at, max_age_seconds=max_age_seconds)
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
                'meaningful_idle_seconds': SITE_CAPTURE_MEANINGFUL_IDLE_SECONDS,
                'last_progress_age_seconds': last_progress_age,
                'last_stage': last_payload.get('stage', ''),
                'last_message': last_payload.get('message', ''),
                'reason': live_reason,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return False

    clear_site_df(operation, 'captura_travada_auto_timeout_sem_progresso_recente')
    set_capture_state(
        operation=operation,
        running=False,
        finished=False,
        error='A captura anterior ficou sem progresso recente e foi destravada. Execute novamente. O próximo lote será menor e mais rápido.',
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
            'last_progress_age_seconds': last_progress_age,
            'last_stage': last_payload.get('stage', ''),
            'last_message': last_payload.get('message', ''),
            'reason': live_reason,
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
