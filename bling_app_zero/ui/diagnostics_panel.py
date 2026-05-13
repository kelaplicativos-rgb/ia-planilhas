from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.engines.ai_scraper_assist import validate_openai_connection
except Exception:
    validate_openai_connection = None

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.flows.simulation import run_all_simulations, run_engine_inventory, run_single_simulation, simulation_options

RESPONSIBLE_FILE = 'bling_app_zero/ui/diagnostics_panel.py'


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
        st.success('Fluxos conferidos sem erro na simulação offline.')
    else:
        st.warning('Alguns fluxos precisam de atenção. Abra o resultado acima para ver a mensagem.')


def _render_engine_inventory() -> None:
    st.markdown('##### Recursos internos')
    show_inventory = st.checkbox('Mostrar recursos carregados', value=False, key='show_engine_inventory')
    if show_inventory:
        st.dataframe(run_engine_inventory(), use_container_width=True, height=220)


def _run_and_store_simulation(key: str) -> None:
    result = run_single_simulation(key)
    st.session_state['blingflow_simulation_result'] = result
    add_audit_event(
        'single_flow_simulation_run',
        area='DIAGNOSTICO',
        details={'simulation_key': key, 'responsible_file': RESPONSIBLE_FILE},
    )


def _render_flow_simulation_buttons() -> None:
    st.markdown('##### Simular fluxos em busca de erros')
    st.caption('Cada botão roda uma simulação offline do fluxo, sem importar dados reais e sem alterar o sistema.')

    options = simulation_options()
    for index in range(0, len(options), 2):
        cols = st.columns(2)
        for offset, column in enumerate(cols):
            if index + offset >= len(options):
                continue
            key, label = options[index + offset]
            with column:
                if st.button(label, use_container_width=True, key=f'run_single_simulation_{key}'):
                    _run_and_store_simulation(key)

    if st.button('Simular todos os fluxos', use_container_width=True, key='run_blingflow_simulation'):
        st.session_state['blingflow_simulation_result'] = run_all_simulations()
        add_audit_event(
            'all_flow_simulations_run',
            area='DIAGNOSTICO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )


def render_diagnostics_content() -> None:
    st.caption('Use esta área para testar rapidamente os fluxos principais sem importar arquivos reais.')
    _render_openai_validation()
    _render_engine_inventory()
    _render_flow_simulation_buttons()

    result = st.session_state.get('blingflow_simulation_result')
    if isinstance(result, pd.DataFrame):
        _render_simulation_result(result)


def render_diagnostics_panel() -> None:
    with st.sidebar:
        with st.expander('Ferramentas de conferência', expanded=False):
            render_diagnostics_content()


__all__ = ['render_diagnostics_content', 'render_diagnostics_panel']
