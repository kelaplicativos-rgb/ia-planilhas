from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_outputs import build_stock_outputs, build_stock_outputs_from_dataframe, render_stock_outputs
from bling_app_zero.ui.estoque_sources import get_estoque_site_source, render_estoque_upload, source_files_from_upload
from bling_app_zero.ui.home_shared import df_signature, preview_df

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _render_header() -> None:
    st.markdown('### Atualização de estoque')
    st.caption('Preencha somente as colunas pedidas pelo modelo de estoque do Bling. Campo não encontrado fica vazio.')


def _render_upload_step(home_model_loaded: bool):
    if home_model_loaded:
        st.success('Modelo de estoque carregado. Agora envie a origem do fornecedor.')
    return render_estoque_upload(home_model_loaded)


def _current_source_signature(df_origem_site: pd.DataFrame | None, upload) -> str:
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        return 'site:' + df_signature(df_origem_site)
    files = source_files_from_upload(upload)
    names = [str(getattr(file, 'name', 'arquivo')) for file in files]
    sizes = [str(getattr(file, 'size', '')) for file in files]
    return 'upload:' + '|'.join(names + sizes)


def _clear_estoque_outputs_if_source_changed(df_origem_site: pd.DataFrame | None, upload) -> None:
    signature = _current_source_signature(df_origem_site, upload)
    previous = st.session_state.get(ESTOQUE_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    for key in [
        'estoque_multi_outputs',
        'df_final_estoque',
        'mapping_estoque',
    ]:
        st.session_state.pop(key, None)
    st.session_state[ESTOQUE_SOURCE_SIGNATURE_KEY] = signature


def _render_model_required_warning(df_modelo: pd.DataFrame | None) -> bool:
    if _valid_model(df_modelo):
        return False
    st.error('Envie o modelo de estoque do Bling antes de gerar o CSV. O sistema só vai preencher as colunas existentes nesse modelo.')
    return True


def _render_site_origin_actions(df_origem_site: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    st.success('Origem criada pelo site carregada para atualização de estoque.')
    preview_df('Origem de estoque criada pelo site', df_origem_site)
    missing_model = _render_model_required_warning(df_modelo)
    if st.button('Gerar CSV de estoque', use_container_width=True, key='gerar_csv_estoque_site', disabled=missing_model):
        build_stock_outputs_from_dataframe(df_origem_site, df_modelo, deposito, name='Origem criada pelo site')


def _render_upload_origin_actions(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    source_files = source_files_from_upload(upload)
    if len(source_files) > 1:
        st.info(f'{len(source_files)} origens detectadas. Será gerado um CSV final para cada uma.')

    missing_model = _render_model_required_warning(df_modelo)
    if st.button('Gerar CSV de estoque', use_container_width=True, key='gerar_csv_estoque_upload', disabled=missing_model):
        build_stock_outputs(upload, df_modelo, deposito)


def _render_empty_state(home_model_loaded: bool) -> None:
    if home_model_loaded:
        st.info('Envie a origem do fornecedor para gerar o CSV final de estoque.')
    else:
        st.info('Envie a origem do fornecedor e o modelo de estoque do Bling.')


def render_estoque_panel() -> None:
    _render_header()

    model_loaded = home_estoque_model_loaded()
    upload = _render_upload_step(model_loaded)
    df_origem_site = get_estoque_site_source()
    _clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)

    deposito = st.text_input('Nome do depósito', value='Não definido', key='estoque_nome_deposito')

    if isinstance(df_origem_site, pd.DataFrame):
        _render_site_origin_actions(df_origem_site, df_modelo, deposito)
    elif upload.attachments:
        _render_upload_origin_actions(upload, df_modelo, deposito)
    else:
        _render_empty_state(model_loaded)

    render_stock_outputs()
