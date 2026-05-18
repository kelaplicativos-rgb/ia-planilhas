from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.ai_analysis_panel import render_ai_origin_analysis_panel
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
    site_origin = is_site_origin()
    if not site_origin:
        st.markdown('### Envie a origem dos dados')
        st.caption('Planilha, XML, PDF, HTML ou CSV do fornecedor, ERP, marketplace ou outro sistema.')

    df_origem_site = get_site_source_for_operation('cadastro') if site_origin else None
    upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)
    store_cadastro_context(df_origem, df_modelo, df_modelo_estoque)

    if valid_df(df_origem) and site_origin:
        st.success(f'Origem pronta: {len(df_origem)} registro(s).')
        render_ai_origin_analysis_panel(df_origem, df_modelo, operation='cadastro')
    elif valid_df(df_origem):
        st.success(f'Origem carregada: {len(df_origem)} registro(s).')
        render_ai_origin_analysis_panel(df_origem, df_modelo, operation='cadastro')
        with st.expander('Ver origem dos dados', expanded=False):
            preview_df('Origem dos dados', df_origem)
    elif site_origin:
        st.info('Busque os dados pelo site para liberar o mapeamento.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.info('Envie o arquivo do fornecedor, ERP, marketplace ou outro sistema.')

    if not valid_model(df_modelo):
        st.error('Modelo de destino ausente. Volte em Modelo e envie o arquivo correto.')


__all__ = [
    'empty_cadastro_upload_result',
    'render_cadastro_entrada_step',
    'source_dataframe',
]
