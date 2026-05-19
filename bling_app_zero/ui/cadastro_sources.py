from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_models import cadastro_default_model, estoque_default_model
from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.smart_upload import SmartUploadResult, SUPPORTED_TYPES, render_smart_upload_box

SUPPLIER_OPERATION = 'fornecedor'


def _valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def select_cadastro_model(upload) -> pd.DataFrame:
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
    if isinstance(df_origem_site, pd.DataFrame):
        return _site_origin_upload_result(df_origem_site)

    return render_smart_upload_box(
        title='Dados do fornecedor',
        operation=SUPPLIER_OPERATION,
        key='smart_upload_fornecedor',
        allow_model=False,
        required_model=False,
        accepted_types=SUPPORTED_TYPES,
    )
