from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.ai_analysis_panel import render_ai_origin_analysis_panel
from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_sources import get_estoque_site_source, render_estoque_upload, source_files_from_upload
from bling_app_zero.ui.estoque_wizard_state import (
    ESTOQUE_DEPOSITO_KEY,
    clear_estoque_outputs_if_deposito_changed,
    clear_estoque_outputs_if_source_changed,
    deposito_value,
    is_site_origin,
    normalize_deposito,
    store_deposito_value,
    store_estoque_context,
    valid_model,
)
from bling_app_zero.ui.home_models import get_home_estoque_model
from bling_app_zero.ui.smart_upload import SmartUploadResult


def empty_estoque_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        model_df=get_home_estoque_model(),
        cadastro_model_file=None,
        cadastro_model_df=None,
        estoque_model_file=None,
        estoque_model_df=get_home_estoque_model(),
        attachments=[],
        ignored_files=[],
    )


def render_deposito_input() -> str:
    current = deposito_value()
    if ESTOQUE_DEPOSITO_KEY not in st.session_state:
        st.session_state[ESTOQUE_DEPOSITO_KEY] = current

    deposito = st.text_input(
        'Depósito',
        value=current,
        key=ESTOQUE_DEPOSITO_KEY,
        placeholder='Ex: Principal',
        help='Valor aplicado nas colunas de depósito da planilha final.',
    )
    deposito = normalize_deposito(deposito)
    store_deposito_value(deposito, write_primary=False)
    clear_estoque_outputs_if_deposito_changed(deposito)
    if deposito:
        st.success(f'Depósito: {deposito}')
    else:
        st.error('Informe o depósito.')
    return deposito


def render_deposito_missing_recovery() -> str:
    st.warning('Informe o depósito para gerar o estoque.')
    deposito = render_deposito_input()
    if not deposito:
        st.error('Geração bloqueada: a planilha final de estoque precisa do depósito.')
    return deposito


def _source_dataframe_from_upload_or_site(df_origem_site: pd.DataFrame | None, upload: SmartUploadResult) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame):
        return df_origem_site
    source_df = getattr(upload, 'source_df', None)
    return source_df if isinstance(source_df, pd.DataFrame) else None


def render_estoque_entrada_step() -> None:
    site_origin = is_site_origin()
    if not site_origin:
        st.markdown('### Envie a origem')
        st.caption('Arquivo do fornecedor para atualizar estoque.')

    deposito = render_deposito_input()

    model_loaded = home_estoque_model_loaded()
    site_origin = is_site_origin()
    df_origem_site = get_estoque_site_source() if site_origin else None
    upload = empty_estoque_upload_result() if site_origin else render_estoque_upload(model_loaded)
    clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)
    store_estoque_context(upload, df_origem_site, df_modelo)
    df_origem = _source_dataframe_from_upload_or_site(df_origem_site, upload)

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty and site_origin:
        st.success('Origem por site pronta.')
        render_ai_origin_analysis_panel(df_origem_site, df_modelo, operation='estoque')
    elif site_origin:
        st.info('Busque os produtos pelo site para liberar a geração.')
    else:
        source_files = source_files_from_upload(upload)
        if source_files:
            st.success(f'{len(source_files)} arquivo(s) detectado(s).')
            render_ai_origin_analysis_panel(df_origem, df_modelo, operation='estoque')
        else:
            st.info('Envie o arquivo do fornecedor.')

    if not valid_model(df_modelo):
        st.error('Modelo de estoque ausente.')
    elif not deposito:
        st.error('Informe o depósito antes de continuar.')


__all__ = [
    'empty_estoque_upload_result',
    'render_deposito_input',
    'render_deposito_missing_recovery',
    'render_estoque_entrada_step',
]
