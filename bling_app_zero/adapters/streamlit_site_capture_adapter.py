from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from bling_app_zero.core.site_capture_engine import SiteCaptureCommandResult, build_capture_report, fail_capture, finish_capture, start_capture
from bling_app_zero.core.site_capture_state import SiteCaptureRequest, SiteCaptureState

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_site_capture_adapter.py'
SITE_CAPTURE_STATE_KEY = 'neutral_site_capture_state_v1'
SITE_CAPTURE_REPORT_KEY = 'neutral_site_capture_report_v1'


@dataclass(frozen=True)
class StreamlitSiteCaptureResult:
    handled: bool
    needs_rerun: bool = False
    message: str = ''
    data_key: str = ''
    origin_key: str = ''


def request_from_streamlit(values: Mapping[str, Any] | None = None) -> SiteCaptureRequest:
    merged: dict[str, Any] = dict(st.session_state)
    if values:
        merged.update(dict(values))
    return SiteCaptureRequest.from_mapping(merged)


def site_capture_state_from_streamlit() -> SiteCaptureState:
    stored = st.session_state.get(SITE_CAPTURE_STATE_KEY)
    if isinstance(stored, Mapping):
        return SiteCaptureState.from_mapping(stored)
    return SiteCaptureState.from_mapping(dict(st.session_state))


def sync_site_capture_to_streamlit(result: SiteCaptureCommandResult, *, data: Any = None) -> None:
    st.session_state[SITE_CAPTURE_STATE_KEY] = result.state.to_dict()
    st.session_state[SITE_CAPTURE_REPORT_KEY] = build_capture_report(result)
    if data is not None:
        st.session_state[result.data_key] = data
        st.session_state[result.origin_key] = data
        st.session_state['df_site_bruto'] = data
        st.session_state['df_origem_site_como_planilha'] = data
    st.session_state['site_capture_status'] = result.state.progress.status
    st.session_state['site_capture_message'] = result.message
    st.session_state['site_capture_rows'] = result.state.result.rows or result.state.progress.rows


def start_site_capture(values: Mapping[str, Any] | None = None) -> StreamlitSiteCaptureResult:
    request = request_from_streamlit(values)
    result = start_capture(request)
    sync_site_capture_to_streamlit(result)
    return StreamlitSiteCaptureResult(True, result.needs_rerun, result.message, result.data_key, result.origin_key)


def finish_site_capture(data: Any, values: Mapping[str, Any] | None = None, *, report_key: str = '', message: str = '') -> StreamlitSiteCaptureResult:
    request = request_from_streamlit(values)
    result = finish_capture(request, data, report_key=report_key, message=message)
    sync_site_capture_to_streamlit(result, data=data)
    return StreamlitSiteCaptureResult(True, result.needs_rerun, result.message, result.data_key, result.origin_key)


def fail_site_capture(error: object, values: Mapping[str, Any] | None = None) -> StreamlitSiteCaptureResult:
    request = request_from_streamlit(values)
    result = fail_capture(request, error)
    sync_site_capture_to_streamlit(result)
    return StreamlitSiteCaptureResult(True, result.needs_rerun, result.message, result.data_key, result.origin_key)


__all__ = [
    'SITE_CAPTURE_REPORT_KEY',
    'SITE_CAPTURE_STATE_KEY',
    'StreamlitSiteCaptureResult',
    'fail_site_capture',
    'finish_site_capture',
    'request_from_streamlit',
    'site_capture_state_from_streamlit',
    'start_site_capture',
    'sync_site_capture_to_streamlit',
]
