from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.flow_spine_output import output_diagnostics, output_is_api, output_plan
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    cadastro_mapping_ready,
    ensure_api_direct_final_df,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_mapping_step.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'


def _is_api_context() -> bool:
    try:
        return output_is_api()
    except Exception:
        return str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower() == CONTEXT_BLING_API


def _operation_label() -> str:
    try:
        plan = output_plan()
        return str(plan.primary_action_label or plan.operation or '').strip()
    except Exception:
        return ''


def _render_mapping_spine_caption() -> None:
    try:
        plan = output_plan()
        st.caption(f"Fluxo ativo: {plan.contract_key} · destino: {plan.final_destination} · operação: universal")
        st.session_state['flow_spine_mapping_ready'] = True
        st.session_state['flow_spine_mapping_diagnostics'] = output_diagnostics()
    except Exception:
        pass


def _render_post_mapping_notice() -> None:
    if not cadastro_mapping_ready():
        st.info('Confirme o mapeamento para liberar a revisão, a prévia e o download.')
        return

    if _is_api_context():
        label = _operation_label() or 'enviar'
        st.success(f'Mapeamento confirmado. Continue para a prévia e {label}.')
        return

    st.success('Mapeamento confirmado. O download será liberado no final, após a revisão e a prévia.')


def _df_for_mapping(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado
    return df_origem


def render_cadastro_mapeamento_step() -> None:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    _render_mapping_spine_caption()

    if not valid_df(df_origem):
        st.warning('Nenhuma planilha com dados carregada. Volte para Dados importados.')
        return

    store_expected_source_rows(df_origem)

    if _is_api_context():
        df_final = ensure_api_direct_final_df()
        if valid_df(df_final):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric('Linhas carregadas', len(df_origem))
            with col_b:
                st.metric('Campos preparados', len(df_final.columns))
            st.info('Modo de envio: mapeamento manual dispensado. O fluxo seguirá com os campos preparados.')
            _render_post_mapping_notice()
            return

    if not valid_model(df_modelo):
        st.warning('Modelo para mapear ausente. Volte para Modelo para mapear.')
        return

    df_para_mapear = _df_for_mapping(df_origem)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric('Linhas encontradas', len(df_origem))
    with col_b:
        st.metric('Colunas do modelo', len(df_modelo.columns))

    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado na etapa anterior. O valor calculado está disponível para o mapeamento.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = st.session_state.get('df_final_cadastro')
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        if render_row_count_blocker(df_final):
            return

    _render_post_mapping_notice()


__all__ = ['render_cadastro_mapeamento_step']
