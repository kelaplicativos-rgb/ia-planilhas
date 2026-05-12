from __future__ import annotations

import pandas as pd
import streamlit as st

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
        'Nome do depósito que será gravado no CSV',
        value=current,
        key=ESTOQUE_DEPOSITO_KEY,
        placeholder='Ex: Principal, Loja 1, Galpão Central',
        help='Este valor será aplicado em toda coluna de depósito do modelo de estoque do Bling.',
    )
    deposito = normalize_deposito(deposito)
    store_deposito_value(deposito, write_primary=False)
    clear_estoque_outputs_if_deposito_changed(deposito)
    if deposito:
        st.success(f'Depósito definido para o CSV: {deposito}')
    else:
        st.error('Informe o nome real do depósito antes de continuar. Não use “Não definido” nesta etapa.')
    return deposito


def render_deposito_missing_recovery() -> str:
    st.warning('O nome do depósito não chegou nesta etapa. Informe abaixo para gerar o estoque sem voltar no fluxo.')
    deposito = render_deposito_input()
    if not deposito:
        st.error('Geração bloqueada: o CSV de estoque precisa do depósito para preencher o modelo do Bling.')
    return deposito


def render_estoque_entrada_step() -> None:
    st.markdown('### Entrada do estoque')
    st.caption('Nesta tela entra somente a origem de estoque e o nome do depósito. O mapeamento, preview e download ficam nas próximas etapas.')

    deposito = render_deposito_input()

    model_loaded = home_estoque_model_loaded()
    if model_loaded:
        st.success('Modelo de estoque carregado. Agora informe a origem escolhida.')

    site_origin = is_site_origin()
    df_origem_site = get_estoque_site_source() if site_origin else None
    upload = empty_estoque_upload_result() if site_origin else render_estoque_upload(model_loaded)
    clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)
    store_estoque_context(upload, df_origem_site, df_modelo)

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty and site_origin:
        st.success('Origem de estoque por site pronta. Continue para conferir o mapeamento.')
    elif site_origin:
        st.info('Faça a busca por site acima. Quando a origem for criada, o botão Continuar será liberado.')
    else:
        source_files = source_files_from_upload(upload)
        if source_files:
            st.success(f'{len(source_files)} arquivo(s) de origem de estoque detectado(s).')
        else:
            st.info('Envie a origem do fornecedor para gerar o CSV final de estoque.')

    if not valid_model(df_modelo):
        st.error('Envie o modelo de estoque do Bling antes de continuar.')
    elif not deposito:
        st.error('Informe o nome do depósito antes de continuar.')


__all__ = [
    'empty_estoque_upload_result',
    'render_deposito_input',
    'render_deposito_missing_recovery',
    'render_estoque_entrada_step',
]
