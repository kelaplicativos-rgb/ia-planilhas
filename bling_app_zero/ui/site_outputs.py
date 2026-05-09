from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import config_for_site_operation, normalize_site_operation
from bling_app_zero.ui.home_models import save_home_models
from bling_app_zero.ui.home_shared import preview_df
from bling_app_zero.ui.site_progress import render_site_progress_history


def source_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


def _label(operation: str) -> str:
    return 'estoque' if normalize_site_operation(operation) == 'estoque' else 'cadastro'


def go_to_main_flow(operation: str) -> None:
    normalized = normalize_site_operation(operation)
    try:
        st.query_params['flow'] = 'planilha'
        st.query_params['operacao'] = normalized
        st.query_params['origem'] = 'arquivo'
    except Exception:
        pass

    st.session_state['tipo_operacao'] = normalized
    st.session_state['operacao_final'] = normalized
    st.session_state['tipo_operacao_final'] = normalized
    st.session_state['origem_final'] = 'arquivo'
    st.session_state['origem_dados'] = 'planilha'
    st.session_state['origem_tipo'] = 'planilha'
    st.session_state['home_slim_flow_origin'] = 'arquivo'
    st.session_state['home_slim_flow_operation'] = normalized
    st.session_state['home_slim_active_panel'] = normalized


def save_site_source(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    operation: str = 'cadastro',
) -> None:
    normalized = normalize_site_operation(operation)
    save_home_models(df_modelo_cadastro, df_modelo_estoque)
    set_site_source_as_planilha(
        df=df_site,
        operation=normalized,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        cadastro_model_df=df_modelo_cadastro,
        estoque_model_df=df_modelo_estoque,
        operation_model_df=df_modelo,
    )
    st.session_state['operation_site'] = normalized
    st.session_state['tipo_operacao_site'] = normalized
    st.session_state['operacao_final'] = normalized
    st.session_state['origem_final'] = 'site'


def render_generated_site_actions(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    operation: str = 'cadastro',
) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    normalized = normalize_site_operation(operation)
    label = _label(normalized)
    config = config_for_site_operation(normalized)
    st.success(f'Planilha de origem de {label} criada pelo site.')
    render_site_progress_history()
    with st.expander('Ver planilha criada', expanded=False):
        preview_df(f'Planilha criada para {label}', df_site)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            f'Baixar planilha de {label}',
            data=source_csv_bytes(df_site),
            file_name=config.output_filename,
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'download_origem_site_{normalized}_{len(df_site)}_{len(df_site.columns)}',
        )
    with col_b:
        if st.button(f'Continuar para fluxo de {label}', use_container_width=True, key=f'continuar_fluxo_planilha_site_{normalized}'):
            save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, normalized)
            go_to_main_flow(normalized)
            st.rerun()
