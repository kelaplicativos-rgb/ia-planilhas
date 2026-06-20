import streamlit as st

DIAG_KEY = 'flow_stage_diagnostics_v1'
STABLE_STEP_KEY = 'flow_last_stable_step_v1'
VALID_STEPS = {'modelo', 'origem', 'entrada', 'precificacao', 'categorizacao', 'mapeamento', 'regras', 'ia', 'preview', 'download'}


def record_stage(stage, area='FLOW', step=None, status='OK', details=None):
    current = str(step or st.session_state.get('bling_wizard_step') or st.session_state.get('home_wizard_step') or '').strip()
    event = {'stage': str(stage), 'area': str(area), 'step': current, 'status': str(status), 'details': details or {}}
    events = st.session_state.get(DIAG_KEY, [])
    if not isinstance(events, list):
        events = []
    events.append(event)
    st.session_state[DIAG_KEY] = events[-100:]
    if str(status).upper() in {'OK', 'CORRIGIDO'} and current in VALID_STEPS:
        st.session_state[STABLE_STEP_KEY] = current


def repair_state(reason='health_check'):
    corrected = {}
    for key in ('bling_wizard_step', 'home_wizard_step'):
        current = str(st.session_state.get(key) or '').strip().lower()
        if current and current not in VALID_STEPS:
            fallback = str(st.session_state.get(STABLE_STEP_KEY) or 'origem').strip().lower()
            st.session_state[key] = fallback if fallback in VALID_STEPS else 'origem'
            corrected[key] = current
    record_stage('flow_state_repair', area='APP', status='CORRIGIDO' if corrected else 'OK', details={'reason': reason, 'corrected': corrected})
    return corrected
