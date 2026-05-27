from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    get_context_final_df,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_download_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
LEGACY_OPERATION_ALIASES = {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value in {CONTEXT_BLING_API, CONTEXT_BLING_CSV, CONTEXT_UNIVERSAL}:
        return value
    return CONTEXT_UNIVERSAL


def _is_api_context() -> bool:
    return _entry_context() == CONTEXT_BLING_API


def _title() -> str:
    if _is_api_context():
        return 'Envio direto ao Bling'
    if _entry_context() == CONTEXT_BLING_CSV:
        return 'Download CSV Bling'
    return 'Download Modelo Universal'


def _caption() -> str:
    if _is_api_context():
        return 'Envie o resultado final diretamente para o Bling conectado.'
    if _entry_context() == CONTEXT_BLING_CSV:
        return 'Baixe o CSV final no modelo Bling anexado no início.'
    return 'Baixe o arquivo final no modelo universal anexado no início.'


def _normalize_operation(value: object) -> str:
    operation = normalize_contract_operation(value)
    if operation:
        return operation
    text = str(value or '').strip().lower()
    if text in LEGACY_OPERATION_ALIASES:
        return 'universal'
    return ''


def _current_operation() -> str:
    """Resolve a operação real antes de gerar a saída final."""
    for key in (
        MODEL_CONTRACT_TYPE_KEY,
        'df_final_download_operation',
        'final_download_operation',
        'home_slim_flow_operation',
        'home_detected_operation',
        'operacao_final',
        'tipo_operacao_final',
        'tipo_operacao_site',
    ):
        operation = _normalize_operation(st.session_state.get(key))
        if operation:
            return operation

    for key in ('operacao', 'operation', 'operation_v2'):
        try:
            operation = _normalize_operation(st.query_params.get(key, ''))
            if operation:
                return operation
        except Exception:
            pass

    return 'universal'


def _final_df_for_context():
    df_final = get_context_final_df()
    if not _is_api_context():
        df_final = enforce_cadastro_model_columns(df_final)
    return df_final


def render_cadastro_download_step() -> None:
    operation = _current_operation()
    st.markdown(f'### {_title()}')
    st.caption(_caption())

    df_final = _final_df_for_context()
    if not valid_df(df_final):
        st.warning('O resultado final ainda não foi gerado. Volte ao preview.')
        return

    if not _is_api_context() and render_row_count_blocker(df_final):
        return

    st.session_state['df_final_download_operation'] = operation
    download_final(df_final, operation, f'{_entry_context()}_{operation}')


__all__ = ['render_cadastro_download_step']
