from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.engines.ai_scraper_assist import validate_openai_connection
except Exception:
    validate_openai_connection = None

from bling_app_zero.flows.simulation import run_all_simulations, run_engine_inventory


def _render_openai_validation() -> None:
    st.markdown('##### Assistência com IA')

    if validate_openai_connection is None:
        st.caption('Validação de IA indisponível nesta versão.')
        return

    if st.button('Testar conexão da IA', use_container_width=True, key='validate_openai_key'):
        st.session_state['openai_validation_result'] = validate_openai_connection()

    result = st.session_state.get('openai_validation_result')
    if not result:
        st.caption('Opcional. O sistema continua funcionando sem IA configurada.')
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
        st.success('IA conectada.')
    else:
        st.warning('A IA ainda não está pronta. Confira a chave nos secrets.')


def _render_simulation_result(result: pd.DataFrame) -> None:
    st.markdown('##### Resultado da conferência')
    st.dataframe(result, use_container_width=True, height=260)

    failures = result[result['Status'] != 'OK'] if 'Status' in result.columns else result
    if failures.empty:
        st.success('Fluxos principais conferidos sem erro.')
    else:
        st.warning('Alguns fluxos precisam de atenção. Abra o resultado acima para ver a mensagem.')


def render_diagnostics_panel() -> None:
    with st.sidebar:
        with st.expander('Ferramentas de conferência', expanded=False):
            st.caption('Use esta área para testar rapidamente os fluxos principais sem precisar importar arquivos reais.')
            _render_openai_validation()

            st.markdown('##### Recursos internos')
            with st.expander('Ver recursos carregados', expanded=False):
                st.dataframe(run_engine_inventory(), use_container_width=True, height=220)

            if st.button('Conferir fluxos principais', use_container_width=True, key='run_blingflow_simulation'):
                st.session_state['blingflow_simulation_result'] = run_all_simulations()

            result = st.session_state.get('blingflow_simulation_result')
            if isinstance(result, pd.DataFrame):
                _render_simulation_result(result)
