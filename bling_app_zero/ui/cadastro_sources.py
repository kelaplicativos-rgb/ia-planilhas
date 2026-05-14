from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.smart_upload import SmartUploadResult, render_smart_upload_box


def select_cadastro_model(upload) -> pd.DataFrame | None:
    site_model = get_site_model_for_operation('cadastro')
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        save_home_models(upload.cadastro_model_df, upload.estoque_model_df)
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        save_home_models(upload.model_df, upload.estoque_model_df)
        return upload.model_df
    return None


def select_estoque_model_for_cadastro(upload) -> pd.DataFrame | None:
    site_model = get_site_estoque_model()
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else upload.model_df
        save_home_models(cadastro_model, upload.estoque_model_df)
        return upload.estoque_model_df
    return None


def _site_origin_upload_result(df_origem_site: pd.DataFrame) -> SmartUploadResult:
    """Cria um resultado interno sem renderizar novo upload.

    Quando o usuário escolheu busca por site, o resultado do crawler já é a
    origem de dados do fornecedor. Não faz sentido pedir novamente um arquivo
    complementar do fornecedor nesta etapa.
    """
    return SmartUploadResult(
        source_file=None,
        source_df=df_origem_site,
        model_file=None,
        model_df=None,
        cadastro_model_file=None,
        cadastro_model_df=None,
        estoque_model_file=None,
        estoque_model_df=None,
        attachments=[],
        ignored_files=[],
    )


def render_cadastro_source_upload(df_origem_site: pd.DataFrame | None):
    home_has_models = get_home_cadastro_model() is not None or get_home_estoque_model() is not None
    allow_model_upload = not home_has_models

    if isinstance(df_origem_site, pd.DataFrame):
        return _site_origin_upload_result(df_origem_site)

    if home_has_models:
        st.info('Modelo do Bling já carregado. Envie abaixo a planilha, XML, PDF, HTML, MHT ou MHTML do fornecedor.')
    return render_smart_upload_box(
        title='Arquivo do fornecedor',
        operation='cadastro',
        key='smart_upload_cadastro',
        allow_model=allow_model_upload,
        required_model=False,
        accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf', 'html', 'htm', 'mht', 'mhtml'],
    )
