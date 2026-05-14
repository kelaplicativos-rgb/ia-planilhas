from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_models import cadastro_default_model, estoque_default_model
from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.smart_upload import SmartUploadResult, render_smart_upload_box


def _valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def select_cadastro_model(upload) -> pd.DataFrame:
    """Seleciona o contrato de cadastro do Bling.

    Prioridade:
    1. modelo do site/fluxo atual;
    2. modelo salvo na Home;
    3. modelo anexado/classificado como cadastro;
    4. modelo genérico anexado;
    5. modelo interno oficial de cadastro.

    BLINGSCANFIX: cadastro nunca pode ficar sem contrato. Na ausência de planilha
    modelo, o CSV final deve seguir o modelo interno oficial reconhecido pelo Bling.
    """
    site_model = get_site_model_for_operation('cadastro')
    if _valid_model(site_model):
        return site_model.copy().fillna('')

    home_model = get_home_cadastro_model()
    if _valid_model(home_model):
        return home_model.copy().fillna('')

    cadastro_model = getattr(upload, 'cadastro_model_df', None)
    if _valid_model(cadastro_model):
        save_home_models(cadastro_model, getattr(upload, 'estoque_model_df', None))
        return cadastro_model.copy().fillna('')

    generic_model = getattr(upload, 'model_df', None)
    if _valid_model(generic_model):
        save_home_models(generic_model, getattr(upload, 'estoque_model_df', None))
        return generic_model.copy().fillna('')

    return cadastro_default_model()


def select_estoque_model_for_cadastro(upload) -> pd.DataFrame:
    """Seleciona o contrato de estoque auxiliar do cadastro.

    Quando não houver modelo anexado/salvo, usa o contrato interno oficial de
    estoque para manter o fluxo coerente com a regra global do Bling.
    """
    site_model = get_site_estoque_model()
    if _valid_model(site_model):
        return site_model.copy().fillna('')

    home_model = get_home_estoque_model()
    if _valid_model(home_model):
        return home_model.copy().fillna('')

    estoque_model = getattr(upload, 'estoque_model_df', None)
    if _valid_model(estoque_model):
        cadastro_model = getattr(upload, 'cadastro_model_df', None)
        if not _valid_model(cadastro_model):
            cadastro_model = getattr(upload, 'model_df', None)
        save_home_models(cadastro_model if _valid_model(cadastro_model) else None, estoque_model)
        return estoque_model.copy().fillna('')

    return estoque_default_model()


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