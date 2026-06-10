from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_entry_step import (
    empty_cadastro_upload_result as empty_universal_upload_result,
    render_cadastro_entrada_step,
    site_source_dataframe,
    source_dataframe,
)
from bling_app_zero.ui.estoque_entry_step import render_estoque_entrada_step
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation


def _current_contract_operation() -> str:
    for key in (
        MODEL_CONTRACT_TYPE_KEY,
        'home_slim_flow_operation',
        'home_detected_operation',
        'operacao_final',
        'tipo_operacao_final',
        'tipo_operacao_site',
        'operation_site',
    ):
        operation = normalize_contract_operation(st.session_state.get(key))
        if operation:
            return operation
    try:
        operation = normalize_contract_operation(st.query_params.get('operacao', ''))
        if operation:
            return operation
    except Exception:
        pass
    return ''


def render_universal_entrada_step() -> None:
    if _current_contract_operation() == 'estoque':
        render_estoque_entrada_step()
        return
    render_cadastro_entrada_step()


__all__ = [
    'empty_universal_upload_result',
    'render_universal_entrada_step',
    'site_source_dataframe',
    'source_dataframe',
]
