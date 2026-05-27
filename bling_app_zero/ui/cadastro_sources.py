from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, get_home_preco_model, get_home_universal_model, save_home_models
from bling_app_zero.ui.smart_upload import SmartUploadResult, SUPPORTED_TYPES, render_smart_upload_box
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

SUPPLIER_OPERATION = 'fornecedor'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value == 'bling':
        return CONTEXT_BLING_API
    if value in {CONTEXT_BLING_API, CONTEXT_BLING_CSV, CONTEXT_UNIVERSAL}:
        return value
    return CONTEXT_UNIVERSAL


def _operation() -> str:
    for key in ('home_slim_flow_operation', 'home_detected_operation', 'operacao_final', 'tipo_operacao_final'):
        operation = normalize_contract_operation(st.session_state.get(key))
        if operation:
            return operation
    return 'cadastro'


def _valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _copy_model(df: object) -> pd.DataFrame | None:
    return df.copy().fillna('') if _valid_model(df) else None


def _direct_api_model() -> pd.DataFrame | None:
    if _entry_context() != CONTEXT_BLING_API:
        return None
    for key in (DIRECT_API_CONTRACT_KEY, 'cadastro_wizard_df_modelo'):
        copied = _copy_model(st.session_state.get(key))
        if copied is not None:
            return copied
    return None


def _home_bling_model_for_operation() -> pd.DataFrame | None:
    operation = _operation()
    if operation == 'estoque':
        return _copy_model(get_home_estoque_model())
    if operation == 'atualizacao_preco':
        return _copy_model(get_home_preco_model())
    return _copy_model(get_home_cadastro_model())


def select_cadastro_model(upload) -> pd.DataFrame:
    """Seleciona o modelo de destino sem fallback silencioso.

    BLINGRESET:
    - API usa contrato interno.
    - Bling CSV usa apenas modelo Bling real anexado/salvo.
    - Universal usa apenas modelo universal real anexado/salvo.
    """
    direct_model = _direct_api_model()
    if direct_model is not None:
        return direct_model

    context = _entry_context()
    if context == CONTEXT_UNIVERSAL:
        universal_model = _copy_model(get_home_universal_model())
        if universal_model is not None:
            return universal_model
        generic_model = _copy_model(getattr(upload, 'model_df', None))
        if generic_model is not None:
            save_home_models(None, None, None, generic_model, replace_missing=True)
            return generic_model
        return pd.DataFrame()

    site_model = get_site_model_for_operation(_operation())
    if _valid_model(site_model):
        return site_model.copy().fillna('')

    home_model = _home_bling_model_for_operation()
    if home_model is not None:
        return home_model

    cadastro_model = _copy_model(getattr(upload, 'cadastro_model_df', None))
    if cadastro_model is not None:
        save_home_models(cadastro_model, getattr(upload, 'estoque_model_df', None), None, None, replace_missing=True)
        return cadastro_model

    generic_model = _copy_model(getattr(upload, 'model_df', None))
    if generic_model is not None and context != CONTEXT_BLING_CSV:
        save_home_models(generic_model, getattr(upload, 'estoque_model_df', None), None, None, replace_missing=True)
        return generic_model

    return pd.DataFrame()


def select_estoque_model_for_cadastro(upload) -> pd.DataFrame:
    if _entry_context() == CONTEXT_UNIVERSAL:
        return pd.DataFrame()

    site_model = get_site_estoque_model()
    if _valid_model(site_model):
        return site_model.copy().fillna('')

    home_model = get_home_estoque_model()
    if _valid_model(home_model):
        return home_model.copy().fillna('')

    estoque_model = _copy_model(getattr(upload, 'estoque_model_df', None))
    if estoque_model is not None:
        cadastro_model = _copy_model(getattr(upload, 'cadastro_model_df', None)) or _copy_model(getattr(upload, 'model_df', None))
        save_home_models(cadastro_model, estoque_model, None, None, replace_missing=True)
        return estoque_model

    return pd.DataFrame()


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
