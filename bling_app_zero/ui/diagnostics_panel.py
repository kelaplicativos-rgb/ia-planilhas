from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.engines.ai_scraper_assist import validate_openai_connection
from bling_app_zero.flows.simulation import run_all_simulations, run_engine_inventory


def _render_openai_validation() -> None:
    st.markdown('##### Validação da OpenAI')
    st.caption('Este teste verifica se a chave existe e se a API responde. A chave nunca é exibida completa.')

    if st.button('Validar chave OpenAI', use_container_width=True, key='validate_openai_key'):
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
        st.success('OpenAI conectada. O complemento de IA do scraper está ativo.')
    else:
        st.warning('OpenAI ainda não está pronta. Veja a mensagem acima.')


def render_diagnostics_panel() -> None:
    with st.expander('BLINGSCAN / Simulação interna dos fluxos', expanded=False):
        st.caption(
            'Este painel valida se cada recurso possui motor registrado e se os fluxos principais executam '
            'com dados simulados, sem depender de anexos reais.'
        )

        _render_openai_validation()

        st.markdown('##### Motores registrados')
        st.dataframe(run_engine_inventory(), use_container_width=True, height=220)

        if st.button('Executar simulação de todos os fluxos', use_container_width=True, key='run_blingflow_simulation'):
            st.session_state['blingflow_simulation_result'] = run_all_simulations()

        result = st.session_state.get('blingflow_simulation_result')
        if result is not None:
            st.markdown('##### Resultado da simulação')
            st.dataframe(result, use_container_width=True, height=260)

            failures = result[result['Status'] != 'OK'] if 'Status' in result.columns else result
            if failures.empty:
                st.success('Todos os fluxos simulados responderam com sucesso.')
            else:
                st.warning('Algum fluxo precisa de atenção. Veja a tabela acima.')
