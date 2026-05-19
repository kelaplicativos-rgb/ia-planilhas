from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_models import cadastro_default_model, estoque_default_model
from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.smart_upload import SmartUploadResult, SUPPORTED_TYPES, render_smart_upload_box

VALID_OPERATIONS = {'cadastro', 'estoque'}


def _valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _current_operation() -> str:
    for key in (
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
        'home_slim_flow_operation',
        'home_detected_operation',
    ):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in VALID_OPERATIONS:
            return value
    try:
        value = str(st.query_params.get('operacao', '') or '').strip().lower()
        if value in VALID_OPERATIONS:
            return value
    except Exception:
        pass
    return 'cadastro'


def select_cadastro_model(upload) -> pd.DataFrame:
    """Seleciona o contrato de destino para cadastro.

    No fluxo atual, o modelo anexado na primeira etapa tem prioridade absoluta.
    O modelo interno só existe como proteção legada se o fluxo antigo ainda for
    chamado sem modelo salvo.
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
    """Seleciona o contrato de destino auxiliar para estoque."""
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
    """Cria um resultado interno sem renderizar novo upload."""
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

    return render_smart_upload_box(
        title='Arquivo do fornecedor',
        operation=_current_operation(),
        key='smart_upload_cadastro',
        allow_model=allow_model_upload,
        required_model=False,
        accepted_types=SUPPORTED_TYPES,
    )
