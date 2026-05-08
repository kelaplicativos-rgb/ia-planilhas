from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.engines.ai_scraper_assist import validate_openai_connection
except Exception:
    validate_openai_connection = None

from bling_app_zero.flows.simulation import run_all_simulations, run_engine_inventory


def _render_openai_validation() -> None:
    st.markdown('##### OpenAI')

    if validate_openai_connection is None:
        st.caption('Validação indisponível neste build.')
        return

    if st.button('Validar chave', use_container_width=True, key='validate_openai_key'):
        st.session_state['openai_validation_result'] = validate_openai_connection()

    result = st.session_state.get('openai_validation_result')
    if not result:
        return

    df = pd.DataFrame([
        {
            'Status': result.get('status'),
            'Modelo': result.get('model'),
            'Chave': result.get('key') or '(não encontrada)',
            'Mensagem': result.get('message'),
        }
    ])
    st.dataframe(df, use_container_width=True, height=90)

    if result.get('ok'):
        st.success('Conectado.')
    else:
        st.warning('Atenção.')


def render_diagnostics_panel() -> None:
    with st.sidebar:
        with st.expander('Diagnóstico técnico', expanded=False):
            _render_openai_validation()

            st.markdown('##### Motores')
            st.dataframe(run_engine_inventory(), use_container_width=True, height=220)

            if st.button('Simular fluxos', use_container_width=True, key='run_blingflow_simulation'):
                st.session_state['blingflow_simulation_result'] = run_all_simulations()

            result = st.session_state.get('blingflow_simulation_result')
            if result is not None:
                st.markdown('##### Resultado')
                st.dataframe(result, use_container_width=True, height=260)

                failures = result[result['Status'] != 'OK'] if 'Status' in result.columns else result
                if failures.empty:
                    st.success('Tudo certo.')
                else:
                    st.warning('Verificar.')
