from __future__ import annotations

import time

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/startup_guard.py'
BOOT_READY_KEY = 'bling_startup_guard_ready_v1'
BOOT_RENDERED_KEY = 'bling_startup_guard_rendered_once_v1'
BOOT_STARTED_AT_KEY = 'bling_startup_guard_started_at_v1'
RECOVERY_MARK_KEY = 'blingfix_capture_recovery_mark_v1'
RECOVERY_NOTICE_KEY = 'blingfix_capture_recovery_notice_v1'
RECOVERY_SOFT_SECONDS = 90
RECOVERY_HARD_SECONDS = 240

VOLATILE_CAPTURE_KEYS = (
    'site_capture_running',
    'site_capture_finished',
    'site_capture_error',
    'site_capture_result_ready',
    'site_capture_rows',
    'site_capture_columns',
    'site_progress_log',
    'site_progress_last',
    'site_progress_last_seen_at',
    'neutral_site_progress_state_v1',
    'site_progress_callback_last_render_at',
    'site_progress_callback_last_percent',
    'live_operation_progress_last_v1',
    'blingsmartscan_manual_continue_required',
    'blingsmartscan_ready_to_continue',
    'blingsmartscan_continue_target_step',
)

PARTIAL_SITE_KEYS = (
    'df_site_bruto',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
)


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _has_partial_site_result() -> bool:
    try:
        import pandas as pd
    except Exception:
        pd = None
    for key in PARTIAL_SITE_KEYS:
        value = st.session_state.get(key)
        if pd is not None and isinstance(value, pd.DataFrame) and not value.empty:
            return True
    return False


def _recover_interrupted_capture() -> bool:
    if not bool(st.session_state.get('site_capture_running')):
        return False

    now = time.time()
    started_at = _safe_float(st.session_state.get('site_capture_started_at'))
    last_seen_at = _safe_float(st.session_state.get('site_progress_last_seen_at'))
    age = now - started_at if started_at > 0 else RECOVERY_HARD_SECONDS + 1
    idle = now - last_seen_at if last_seen_at > 0 else age
    has_partial = _has_partial_site_result()

    if has_partial and age >= RECOVERY_SOFT_SECONDS:
        reason = 'Busca anterior tinha resultado parcial e foi destravada automaticamente. Confira o resultado salvo ou execute novo lote.'
    elif idle >= RECOVERY_SOFT_SECONDS and age >= RECOVERY_SOFT_SECONDS:
        reason = 'Busca anterior ficou sem sinal vivo e foi destravada automaticamente.'
    elif age >= RECOVERY_HARD_SECONDS:
        reason = 'Busca anterior passou do limite seguro e foi destravada automaticamente.'
    else:
        return False

    mark = f'{int(started_at)}:{int(age)}:{int(idle)}:{has_partial}'
    if st.session_state.get(RECOVERY_MARK_KEY) == mark:
        return False
    st.session_state[RECOVERY_MARK_KEY] = mark

    removed: list[str] = []
    for key in VOLATILE_CAPTURE_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)

    st.session_state['site_capture_running'] = False
    st.session_state['site_capture_finished'] = False
    st.session_state['site_capture_result_ready'] = False
    st.session_state['site_capture_error'] = ''
    st.session_state[RECOVERY_NOTICE_KEY] = reason

    add_audit_event(
        'site_capture_interrupted_session_recovered',
        area='APP',
        status='OK',
        details={
            'age_seconds': round(age, 2),
            'idle_seconds': round(idle, 2),
            'has_partial_site_result': has_partial,
            'removed_keys': removed,
            'preserved_model_origin_and_url': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


def _render_recovery_notice() -> None:
    notice = str(st.session_state.pop(RECOVERY_NOTICE_KEY, '') or '').strip()
    if notice:
        st.warning(notice)
        st.caption('A limpeza foi parcial: modelo, URL, operação e arquivos foram preservados.')


def ensure_app_ready() -> bool:
    """Estabiliza a sessão sem forçar rerun na primeira renderização."""
    _recover_interrupted_capture()
    _render_recovery_notice()

    if bool(st.session_state.get(BOOT_READY_KEY)):
        return True

    if BOOT_STARTED_AT_KEY not in st.session_state:
        st.session_state[BOOT_STARTED_AT_KEY] = time.time()

    if not bool(st.session_state.get(BOOT_RENDERED_KEY)):
        st.session_state[BOOT_RENDERED_KEY] = True
        add_audit_event(
            'startup_guard_first_render_stabilized_without_rerun',
            area='APP',
            status='INFO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        notice = st.empty()
        progress = st.progress(20, text='Inicializando conexão segura da tela...')
        notice.info('Preparando sessão do sistema...')
        time.sleep(0.35)
        try:
            progress.progress(100, text='Sessão pronta.')
            time.sleep(0.05)
            progress.empty()
            notice.empty()
        except Exception:
            pass

    st.session_state[BOOT_READY_KEY] = True
    elapsed = round(time.time() - float(st.session_state.get(BOOT_STARTED_AT_KEY) or time.time()), 2)
    add_audit_event(
        'startup_guard_ready',
        area='APP',
        status='OK',
        details={'elapsed_seconds': elapsed, 'no_startup_rerun': True, 'capture_recovery_enabled': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


def is_app_ready() -> bool:
    return bool(st.session_state.get(BOOT_READY_KEY))


__all__ = ['ensure_app_ready', 'is_app_ready']
