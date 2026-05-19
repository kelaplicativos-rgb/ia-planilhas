from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.cadastro_sources import render_cadastro_source_upload, select_cadastro_model
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

SOURCE_FLOW_OPERATION = 'fornecedor'


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


def _destination_model(upload) -> pd.DataFrame:
    model = get_home_cadastro_model()
    if isinstance(model, pd.DataFrame) and len(model.columns):
        return model.copy().fillna('')

    estoque_model = get_home_estoque_model()
    if isinstance(estoque_model, pd.DataFrame) and len(estoque_model.columns):
        return estoque_model.copy().fillna('')

    return select_cadastro_model(upload)


def render_cadastro_entrada_step() -> None:
    site_origin = is_site_origin()

    df_origem_site = get_site_source_for_operation(SOURCE_FLOW_OPERATION) if site_origin else None
    upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = _destination_model(upload)
    store_cadastro_context(df_origem, df_modelo, None)

    if valid_df(df_origem):
        origem_nome = 'Busca do site' if site_origin else 'Dados do fornecedor'
        st.success(f'{origem_nome} carregados com sucesso. {len(df_origem)} linha(s) encontradas. Próximo passo: mapear com o modelo.')
        with st.expander('Ver dados do fornecedor', expanded=False):
            preview_df('Dados do fornecedor', df_origem)
    elif site_origin:
        st.warning('Busque os dados no site para continuar.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.warning('Envie os dados do fornecedor para continuar.')

    if not valid_model(df_modelo):
        st.error('Modelo de destino ausente. Volte na primeira etapa e envie a planilha modelo.')


__all__ = [
    'empty_cadastro_upload_result',
    'render_cadastro_entrada_step',
    'source_dataframe',
]
