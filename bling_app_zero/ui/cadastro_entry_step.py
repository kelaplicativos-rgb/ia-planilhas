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
from bling_app_zero.ui.flow_context import (
    is_api_direct_mode as _is_api_context,
    is_bling_csv_context as _is_bling_csv_context,
    is_universal_context as _is_universal_context,
)
from bling_app_zero.ui.home_models import (
    get_home_cadastro_model,
    get_home_estoque_model,
    get_home_preco_model,
    get_home_universal_model,
)
from bling_app_zero.ui.home_shared import df_signature, preview_df
from bling_app_zero.ui.home_wizard_constants import STEP_LABELS, STEP_PRECIFICACAO, WIZARD_STEP_KEY
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target
from bling_app_zero.ui.smart_upload import SmartUploadResult

SITE_SOURCE_FALLBACK_KEYS = (
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto',
)
SITE_SOURCE_OPERATIONS = ('universal', 'cadastro', 'estoque', 'fornecedor')
RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_entry_step.py'
ENTRY_AUTOSCROLL_SIGNATURE_KEY = 'cadastro_entry_autoscroll_signature'
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'


def _step_label(step: str) -> str:
    return str(STEP_LABELS.get(step, step)).strip()


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')
    return None


def _copy_model(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def _first_existing_model(*models: pd.DataFrame | None) -> pd.DataFrame | None:
    """Retorna o primeiro modelo válido sem avaliar DataFrame como booleano."""
    for model in models:
        copied = _copy_model(model)
        if copied is not None:
            return copied
    return None


def _direct_api_model() -> pd.DataFrame | None:
    if not _is_api_context():
        return None
    for key in (
        DIRECT_API_CONTRACT_KEY,
        'cadastro_wizard_df_modelo',
    ):
        copied = _copy_model(st.session_state.get(key))
        if copied is not None:
            return copied
    return None


def _bling_contract_model() -> pd.DataFrame | None:
    return _first_existing_model(
        get_home_cadastro_model(),
        get_home_estoque_model(),
        get_home_preco_model(),
    )


def _universal_contract_model() -> pd.DataFrame | None:
    return _copy_model(get_home_universal_model())


def _first_contract_model() -> pd.DataFrame | None:
    direct_model = _direct_api_model()
    if direct_model is not None:
        return direct_model
    if _is_universal_context():
        return _universal_contract_model()
    if _is_bling_csv_context():
        return _bling_contract_model()
    return _first_existing_model(_bling_contract_model(), _universal_contract_model())


def empty_cadastro_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        cadastro_model_file=None,
        cadastro_model_df=_first_contract_model(),
        estoque_model_file=None,
        estoque_model_df=get_home_estoque_model() if _is_bling_csv_context() else None,
        attachments=[],
        ignored_files=[],
    )


def site_source_dataframe() -> pd.DataFrame | None:
    """Busca a origem do site em todas as chaves usadas pelo fluxo atual."""
    for operation in SITE_SOURCE_OPERATIONS:
        df = get_site_source_for_operation(operation)
        copied = _copy_df(df)
        if copied is not None:
            st.session_state['cadastro_entry_site_source_resolved_from'] = f'operation:{operation}'
            return copied

    for key in SITE_SOURCE_FALLBACK_KEYS:
        copied = _copy_df(st.session_state.get(key))
        if copied is not None:
            st.session_state['cadastro_entry_site_source_resolved_from'] = f'key:{key}'
            return copied

    return None


def source_dataframe(df_origem_site: pd.DataFrame | None, upload) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        return df_origem_site.copy().fillna('')
    source_df = getattr(upload, 'source_df', None)
    return source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) and not source_df.empty else None


def _destination_model(upload) -> pd.DataFrame:
    direct_model = _direct_api_model()
    if direct_model is not None:
        return direct_model

    if _is_universal_context():
        universal_model = _universal_contract_model()
        if universal_model is not None:
            return universal_model
    elif _is_bling_csv_context():
        bling_model = _bling_contract_model()
        if bling_model is not None:
            return bling_model
    else:
        fallback_model = _first_existing_model(_bling_contract_model(), _universal_contract_model())
        if fallback_model is not None:
            return fallback_model

    return select_cadastro_model(upload)


def _auto_advance_after_source_loaded(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    if not valid_df(df_origem) or not valid_model(df_modelo):
        return
    signature = df_signature(df_origem) + ':' + df_signature(df_modelo)
    if st.session_state.get(ENTRY_AUTOSCROLL_SIGNATURE_KEY) == signature:
        return
    st.session_state[ENTRY_AUTOSCROLL_SIGNATURE_KEY] = signature
    st.session_state[WIZARD_STEP_KEY] = STEP_PRECIFICACAO
    set_scroll_target(STEP_PRECIFICACAO)
    try:
        st.query_params['step'] = STEP_PRECIFICACAO
    except Exception:
        pass
    st.rerun()


def render_cadastro_entrada_step() -> None:
    site_origin = is_site_origin()

    df_origem_site = site_source_dataframe() if site_origin else None
    upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = _destination_model(upload)
    store_cadastro_context(df_origem, df_modelo, None)

    if valid_df(df_origem):
        origem_nome = 'Busca do site' if site_origin else 'Dados importados'
        proxima_etapa = _step_label(STEP_PRECIFICACAO)
        st.success(f'{origem_nome} carregados com sucesso. {len(df_origem)} linha(s) encontradas. Próxima etapa: {proxima_etapa}.')
        if site_origin:
            resolved_from = str(st.session_state.get('cadastro_entry_site_source_resolved_from') or '').strip()
            if resolved_from:
                st.caption(f'Origem do site vinculada ao fluxo: {resolved_from}.')
        with st.expander('Ver dados importados', expanded=False):
            preview_df('Dados importados', df_origem)
        _auto_advance_after_source_loaded(df_origem, df_modelo)
    elif site_origin:
        st.warning('Busque os dados no site para continuar.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.warning('Envie os dados para continuar.')

    if not valid_model(df_modelo):
        if _is_api_context():
            st.error('Contrato interno da API não foi carregado. Volte ao início do caminho Bling API e selecione o envio direto.')
        else:
            st.error('Modelo de destino ausente. Volte na primeira etapa e envie o modelo que será preenchido no final.')


__all__ = [
    'empty_cadastro_upload_result',
    'render_cadastro_entrada_step',
    'site_source_dataframe',
    'source_dataframe',
]