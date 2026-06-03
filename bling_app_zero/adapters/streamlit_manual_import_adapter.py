from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from bling_app_zero.core.manual_import_engine import ManualImportCommandResult, build_manual_import_report, finish_manual_import
from bling_app_zero.core.manual_import_state import ManualImportRequest, ManualImportState

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_manual_import_adapter.py'
MANUAL_IMPORT_STATE_KEY = 'neutral_manual_import_state_v1'
MANUAL_IMPORT_REPORT_KEY = 'neutral_manual_import_report_v1'


@dataclass(frozen=True)
class StreamlitManualImportResult:
    handled: bool
    ok: bool = False
    needs_rerun: bool = False
    message: str = ''
    data_key: str = ''
    origin_key: str = ''


def request_from_values(values: Mapping[str, Any] | None = None) -> ManualImportRequest:
    merged: dict[str, Any] = dict(st.session_state)
    if values:
        merged.update(dict(values))
    return ManualImportRequest.from_mapping(merged)


def manual_import_state_from_streamlit() -> ManualImportState:
    stored = st.session_state.get(MANUAL_IMPORT_STATE_KEY)
    if isinstance(stored, Mapping):
        return ManualImportState.from_mapping(stored)
    return ManualImportState.from_mapping(dict(st.session_state))


def sync_manual_import_to_streamlit(result: ManualImportCommandResult, *, data: Any = None) -> None:
    st.session_state[MANUAL_IMPORT_STATE_KEY] = result.state.to_dict()
    st.session_state[MANUAL_IMPORT_REPORT_KEY] = build_manual_import_report(result)
    if data is not None and result.state.result.ok:
        st.session_state[result.data_key] = data
        st.session_state[result.origin_key] = data
        st.session_state['df_site_bruto'] = data
        st.session_state['df_origem_site_como_planilha'] = data
    st.session_state['manual_import_status'] = result.state.result.status
    st.session_state['manual_import_message'] = result.message
    st.session_state['manual_import_rows'] = result.state.result.rows


def finish_manual_import_for_streamlit(
    data: Any,
    values: Mapping[str, Any] | None = None,
    *,
    recovery_messages: tuple[str, ...] | list[str] = (),
) -> StreamlitManualImportResult:
    request = request_from_values(values)
    result = finish_manual_import(request, data, recovery_messages=recovery_messages)
    sync_manual_import_to_streamlit(result, data=data)
    return StreamlitManualImportResult(
        handled=True,
        ok=result.state.result.ok,
        needs_rerun=result.needs_rerun,
        message=result.message,
        data_key=result.data_key,
        origin_key=result.origin_key,
    )


__all__ = [
    'MANUAL_IMPORT_REPORT_KEY',
    'MANUAL_IMPORT_STATE_KEY',
    'StreamlitManualImportResult',
    'finish_manual_import_for_streamlit',
    'manual_import_state_from_streamlit',
    'request_from_values',
    'sync_manual_import_to_streamlit',
]
