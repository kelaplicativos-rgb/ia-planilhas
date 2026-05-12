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


def empty_cadastro_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        model_df=None,
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
    st.markdown('### Entrada do cadastro')
    st.caption('Carregue somente a origem do fornecedor nesta etapa. O mapeamento, preview e download ficam nas próximas telas.')

    site_origin = is_site_origin()
    df_origem_site = get_site_source_for_operation('cadastro') if site_origin else None
    upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)
    store_cadastro_context(df_origem, df_modelo, df_modelo_estoque)

    if valid_df(df_origem) and site_origin:
        st.success(f'Origem de cadastro por site pronta com {len(df_origem)} produto(s). Continue para o mapeamento.')
    elif valid_df(df_origem):
        st.success(f'Origem de cadastro carregada com {len(df_origem)} produto(s) e {len(df_origem.columns)} coluna(s).')
        with st.expander('Conferir origem carregada', expanded=False):
            preview_df('Origem do cadastro', df_origem)
    elif site_origin:
        st.info('Faça a busca por site acima. Quando a origem for criada, o botão Continuar será liberado.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.info('Envie a origem do fornecedor antes de continuar.')

    if valid_model(df_modelo):
        st.caption(f'Modelo de cadastro detectado com {len(df_modelo.columns)} coluna(s).')
    else:
        st.error('Modelo de cadastro do Bling ausente. Volte na etapa Modelo e envie o modelo correto antes de continuar.')

    if valid_model(df_modelo_estoque):
        st.caption(f'Modelo de estoque também detectado com {len(df_modelo_estoque.columns)} coluna(s).')


__all__ = [
    'empty_cadastro_upload_result',
    'render_cadastro_entrada_step',
    'source_dataframe',
]
