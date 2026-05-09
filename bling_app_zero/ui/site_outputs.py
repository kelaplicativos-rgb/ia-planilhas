from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import config_for_site_operation
from bling_app_zero.ui.home_models import save_home_models
from bling_app_zero.ui.home_shared import preview_df
from bling_app_zero.ui.site_progress import render_site_progress_history


def source_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


def go_to_main_flow() -> None:
    try:
        st.query_params['flow'] = 'planilha'
    except Exception:
        pass
    st.session_state['tipo_operacao'] = 'cadastro'
    st.session_state['home_slim_flow_step'] = 'planilha'
    st.session_state['home_slim_active_panel'] = 'planilha'


def save_site_source(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    save_home_models(df_modelo_cadastro, df_modelo_estoque)
    set_site_source_as_planilha(
        df=df_site,
        operation='cadastro',
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        cadastro_model_df=df_modelo_cadastro,
        estoque_model_df=df_modelo_estoque,
        operation_model_df=df_modelo,
    )


def render_generated_site_actions(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    config = config_for_site_operation('cadastro')
    st.success('Planilha criada e enviada para o fluxo de planilha.')
    render_site_progress_history()
    with st.expander('Ver planilha criada', expanded=False):
        preview_df('Planilha criada', df_site)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            'Baixar planilha',
            data=source_csv_bytes(df_site),
            file_name=config.output_filename,
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'download_origem_site_unica_{len(df_site)}_{len(df_site.columns)}',
        )
    with col_b:
        if st.button('Continuar', use_container_width=True, key='continuar_fluxo_planilha_site'):
            save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
            go_to_main_flow()
            st.rerun()
