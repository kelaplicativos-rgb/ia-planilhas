from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_outputs import build_stock_outputs, build_stock_outputs_from_dataframe, render_stock_outputs
from bling_app_zero.ui.estoque_sources import get_estoque_site_source, render_estoque_upload, source_files_from_upload
from bling_app_zero.ui.home_shared import preview_df


def _render_header() -> None:
    st.warning('Motor independente de ESTOQUE será carregado somente quando gerar.')
    st.caption('Este fluxo usa somente as colunas pedidas pelo modelo de estoque. Se não encontrar um campo, ele fica vazio.')


def _render_upload_step(home_model_loaded: bool):
    if home_model_loaded:
        st.success('Modelo de estoque já carregado. Envie somente a origem do fornecedor.')
    return render_estoque_upload(home_model_loaded)


def _render_site_origin_actions(df_origem_site: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    st.success('Origem por site carregada como origem de dados. A partir daqui o fluxo é o mesmo da planilha.')
    preview_df('Origem por site para atualização de estoque', df_origem_site)
    if st.button('Gerar atualização de estoque', use_container_width=True):
        build_stock_outputs_from_dataframe(df_origem_site, df_modelo, deposito, name='Origem por site')


def _render_upload_origin_actions(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    source_files = source_files_from_upload(upload)
    if len(source_files) > 1:
        st.info(f'{len(source_files)} origens de estoque detectadas. O sistema vai gerar um CSV final para cada uma.')

    if st.button('Gerar atualização de estoque', use_container_width=True):
        build_stock_outputs(upload, df_modelo, deposito)


def _render_empty_state(home_model_loaded: bool) -> None:
    if home_model_loaded:
        st.info('Anexe a origem do fornecedor para gerar o CSV final.')
    else:
        st.info('Anexe a origem e o modelo de estoque para gerar o CSV final.')


def render_estoque_panel() -> None:
    _render_header()

    model_loaded = home_estoque_model_loaded()
    upload = _render_upload_step(model_loaded)
    df_origem_site = get_estoque_site_source()
    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)

    deposito = st.text_input('Nome do depósito', value='Não definido')

    if isinstance(df_origem_site, pd.DataFrame):
        _render_site_origin_actions(df_origem_site, df_modelo, deposito)
    elif upload.attachments:
        _render_upload_origin_actions(upload, df_modelo, deposito)
    else:
        _render_empty_state(model_loaded)

    render_stock_outputs()
