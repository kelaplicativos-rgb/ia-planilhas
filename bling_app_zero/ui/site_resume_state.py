from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_resume_state.py'
AUTO_RESUME_KEY = 'site_capture_auto_resume_requested'
AUTO_RESUME_OPERATION_KEY = 'site_capture_auto_resume_operation'
AUTO_RESUME_REASON_KEY = 'site_capture_auto_resume_reason'
AUTO_RESUME_ATTEMPTS_KEY = 'site_capture_auto_resume_attempts'
AUTO_RESUME_MAX_ATTEMPTS = 3


def checkpoint_count() -> int:
    payloads = [
        st.session_state.get('site_progress_last'),
        st.session_state.get('live_operation_progress_last_v1'),
    ]
    neutral = st.session_state.get('neutral_site_progress_state_v1')
    if isinstance(neutral, dict):
        payloads.append(neutral.get('last'))
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        count = 0
        try:
            count = int(payload.get('partial_checkpoint_found') or payload.get('found') or 0)
        except Exception:
            count = 0
        rows = payload.get('partial_checkpoint_rows')
        if isinstance(rows, list):
            count = max(count, len(rows))
        if count > 0:
            return count
    return 0


def request_resume(operation: str, reason: str) -> bool:
    operation = str(operation or 'universal').strip().lower() or 'universal'
    attempts = int(st.session_state.get(AUTO_RESUME_ATTEMPTS_KEY) or 0)
    if attempts >= AUTO_RESUME_MAX_ATTEMPTS:
        st.session_state['site_capture_running'] = False
        st.session_state['site_capture_finished'] = False
        st.session_state['site_capture_error'] = 'A busca tentou continuar automaticamente várias vezes. Aperte continuar busca manualmente ou reduza o lote.'
        add_audit_event('site_search_resume_limit_reached', area='SITE', status='AVISO', details={'operation': operation, 'attempts': attempts, 'reason': reason, 'responsible_file': RESPONSIBLE_FILE})
        return False
    st.session_state[AUTO_RESUME_KEY] = True
    st.session_state[AUTO_RESUME_OPERATION_KEY] = operation
    st.session_state[AUTO_RESUME_REASON_KEY] = reason
    st.session_state[AUTO_RESUME_ATTEMPTS_KEY] = attempts + 1
    st.session_state['site_capture_running'] = False
    st.session_state['site_capture_finished'] = False
    st.session_state['site_capture_result_ready'] = False
    st.session_state['site_capture_error'] = 'A busca travou, mas os produtos já localizados foram mantidos. Continuando a busca automaticamente.'
    add_audit_event('site_search_resume_requested', area='SITE', status='OK', details={'operation': operation, 'attempts': attempts + 1, 'checkpoint_count': checkpoint_count(), 'reason': reason, 'responsible_file': RESPONSIBLE_FILE})
    return True


def resume_requested(operation: str) -> bool:
    operation = str(operation or 'universal').strip().lower() or 'universal'
    requested_operation = str(st.session_state.get(AUTO_RESUME_OPERATION_KEY) or operation).strip().lower() or operation
    return bool(st.session_state.get(AUTO_RESUME_KEY)) and requested_operation == operation


def clear_resume_request() -> None:
    st.session_state.pop(AUTO_RESUME_KEY, None)
    st.session_state.pop(AUTO_RESUME_OPERATION_KEY, None)
    st.session_state.pop(AUTO_RESUME_REASON_KEY, None)


__all__ = ['checkpoint_count', 'clear_resume_request', 'request_resume', 'resume_requested']
