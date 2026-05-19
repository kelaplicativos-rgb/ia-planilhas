from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.cadastro_sources import (
    render_cadastro_source_upload,
    select_cadastro_model,
    select_estoque_model_for_cadastro,
)
from bling_app_zero.ui.cadastro_wizard_state import (
    clear_cadastro_outputs_if_source_changed,
    is_site_origin,
    store_cadastro_context,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model
from bling_app_zero.ui.home_shared import preview_df
from bling_app_zero.ui.smart_upload import SmartUploadResult


def current_operation() -> str:
    for key in (
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
        'home_slim_flow_operation',
        'home_detected_operation',
    ):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    try:
        value = str(st.query_params.get('operacao', '') or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    except Exception:
        pass
    return 'cadastro'


def empty_cadastro_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        cadastro_model_file=None,
        cadastro_model_df=get_home_cadastro_model(),
        estoque_model_file=None,
        estoque_model_df=get_home_estoque_model(),
        attachments=[],
        ignored_files=[],
    )


def source_dataframe(df_origem_site: pd.DataFrame | None, upload) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame):
        return df_origem_site
    source_df = getattr(upload, 'source_df', None)
    return source_df if isinstance(source_df, pd.DataFrame) else None


def render_cadastro_entrada_step() -> None:
    operation = current_operation()
    site_origin = is_site_origin()

    df_origem_site = get_site_source_for_operation(operation) if site_origin else None
    upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo_cadastro = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)
    df_modelo = df_modelo_estoque if operation == 'estoque' else df_modelo_cadastro
    store_cadastro_context(df_origem, df_modelo, df_modelo_estoque)

    if valid_df(df_origem):
        origem_nome = 'Busca do site' if site_origin else 'Planilha enviada'
        st.success(f'{origem_nome} com sucesso. {len(df_origem)} produto(s) encontrados. Próximo passo: ligar as colunas.')
        with st.expander('Ver detalhes da planilha', expanded=False):
            preview_df('Planilha enviada', df_origem)
    elif site_origin:
        st.warning('Busque os produtos no site para continuar.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.warning('Envie a planilha de produtos para continuar.')

    if not valid_model(df_modelo):
        st.error('Planilha modelo ausente. Volte em Enviar modelo e envie o arquivo correto.')


__all__ = [
    'current_operation',
    'empty_cadastro_upload_result',
    'render_cadastro_entrada_step',
    'source_dataframe',
]
