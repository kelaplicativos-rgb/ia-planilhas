from __future__ import annotations

import pandas as pd
import streamlit as st

PROGRESS_LOG_KEY = 'site_progress_log'
STATE_KEY = 'neutral_site_capture_state_v1'
REPORT_KEY = 'neutral_site_capture_report_v1'
DF_PROGRESS_KEY = 'df_site_diagnostico_progresso'
DF_STATE_KEY = 'df_site_diagnostico_estado'


def sync_site_diag_frames() -> None:
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    if isinstance(log, list):
        st.session_state[DF_PROGRESS_KEY] = pd.DataFrame([item for item in log if isinstance(item, dict)])
    state = st.session_state.get(STATE_KEY) or {}
    report = st.session_state.get(REPORT_KEY) or {}
    st.session_state[DF_STATE_KEY] = pd.DataFrame([
        {
            'status': st.session_state.get('site_capture_status', ''),
            'message': st.session_state.get('site_capture_message', ''),
            'rows': st.session_state.get('site_capture_rows', 0),
            'state': str(state)[:1000],
            'report': str(report)[:1000],
        }
    ])


__all__ = ['sync_site_diag_frames']
