from __future__ import annotations

import streamlit as st

from bling_app_zero.flows.simulation import run_all_simulations, run_engine_inventory


def render_diagnostics_panel() -> None:
    with st.expander('BLINGSCAN / Simulação interna dos fluxos', expanded=False):
        st.caption(
            'Este painel valida se cada recurso possui motor registrado e se os fluxos principais executam '
            'com dados simulados, sem depender de anexos reais.'
        )

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
