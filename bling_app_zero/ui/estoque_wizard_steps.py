from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_outputs import build_stock_outputs, build_stock_outputs_from_dataframe, render_stock_outputs
from bling_app_zero.ui.estoque_sources import get_estoque_site_source, render_estoque_upload, source_files_from_upload
from bling_app_zero.ui.home_shared import df_signature, preview_df

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'
ESTOQUE_UPLOAD_KEY = 'estoque_wizard_upload'
ESTOQUE_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_MODELO_KEY = 'estoque_wizard_df_modelo'
ESTOQUE_DEPOSITO_KEY = 'estoque_nome_deposito'


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _valid_deposito() -> bool:
    deposito = str(st.session_state.get(ESTOQUE_DEPOSITO_KEY) or '').strip()
    return bool(deposito)


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


def _store_estoque_context(upload, df_origem_site: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    st.session_state[ESTOQUE_UPLOAD_KEY] = upload
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.session_state[ESTOQUE_ORIGEM_SITE_KEY] = df_origem_site
    else:
        st.session_state.pop(ESTOQUE_ORIGEM_SITE_KEY, None)
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        st.session_state[ESTOQUE_MODELO_KEY] = df_modelo
    else:
        st.session_state.pop(ESTOQUE_MODELO_KEY, None)


def estoque_context_ready() -> bool:
    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    df_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    has_site = isinstance(df_site, pd.DataFrame) and not df_site.empty
    has_upload = bool(upload is not None and source_files_from_upload(upload))
    return (has_site or has_upload) and _valid_model(df_modelo) and _valid_deposito()


def estoque_output_ready() -> bool:
    outputs = st.session_state.get('estoque_multi_outputs')
    if isinstance(outputs, list) and outputs:
        return True
    df_final = st.session_state.get('df_final_estoque')
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def render_estoque_entrada_step() -> None:
    st.markdown('### Entrada do estoque')
    st.caption('Nesta tela entra somente a origem de estoque e o nome do depósito. O preview/download ficam nas próximas etapas.')

    model_loaded = home_estoque_model_loaded()
    if model_loaded:
        st.success('Modelo de estoque carregado. Agora envie a origem do fornecedor ou use a busca por site.')

    upload = render_estoque_upload(model_loaded)
    df_origem_site = get_estoque_site_source()
    _clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)
    _store_estoque_context(upload, df_origem_site, df_modelo)

    deposito = st.text_input('Nome do depósito', value=st.session_state.get(ESTOQUE_DEPOSITO_KEY, 'Não definido'), key=ESTOQUE_DEPOSITO_KEY)

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.success(f'Origem de estoque criada pelo site com {len(df_origem_site)} linha(s).')
        with st.expander('Conferir origem de estoque do site', expanded=False):
            preview_df('Origem de estoque criada pelo site', df_origem_site)
    else:
        source_files = source_files_from_upload(upload)
        if source_files:
            st.success(f'{len(source_files)} arquivo(s) de origem de estoque detectado(s).')
        else:
            st.info('Envie a origem do fornecedor para gerar o CSV final de estoque.')

    if not _valid_model(df_modelo):
        st.error('Envie o modelo de estoque do Bling antes de continuar.')
    elif not str(deposito or '').strip():
        st.error('Informe o nome do depósito antes de continuar.')
    else:
        st.caption(f'Depósito definido: {deposito}')


def render_estoque_gerar_step() -> None:
    st.markdown('### Gerar estoque')
    st.caption('Nesta etapa o sistema monta o CSV de estoque. O download fica separado na próxima tela.')

    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    df_origem_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    deposito = str(st.session_state.get(ESTOQUE_DEPOSITO_KEY) or '').strip() or 'Não definido'

    if not _valid_model(df_modelo):
        st.error('Modelo de estoque ausente. Volte para a entrada.')
        return
    if not _valid_deposito():
        st.error('Nome do depósito ausente. Volte para a entrada.')
        return

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.info('Origem de estoque veio da busca por site.')
        if st.button('Gerar preview de estoque', use_container_width=True, key='wizard_gerar_estoque_site'):
            build_stock_outputs_from_dataframe(df_origem_site, df_modelo, deposito, name='Origem criada pelo site')
    elif upload is not None and source_files_from_upload(upload):
        st.info('Origem de estoque veio de arquivo enviado.')
        if st.button('Gerar preview de estoque', use_container_width=True, key='wizard_gerar_estoque_upload'):
            build_stock_outputs(upload, df_modelo, deposito)
    else:
        st.warning('Nenhuma origem de estoque carregada. Volte para a entrada.')
        return

    if estoque_output_ready():
        st.success('Preview de estoque gerado. Continue para conferir e baixar.')


def render_estoque_preview_step() -> None:
    st.markdown('### Preview e download do estoque')
    st.caption('Confira e baixe somente o CSV final de atualização de estoque.')

    if not estoque_output_ready():
        st.warning('O preview de estoque ainda não foi gerado. Volte para Gerar estoque.')
        return
    render_stock_outputs()
