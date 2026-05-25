from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    get_universal_final_df,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_download_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal'}
LEGACY_OPERATION_ALIASES = {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


def _normalize_operation(value: object) -> str:
    operation = str(value or '').strip().lower()
    if operation in LEGACY_OPERATION_ALIASES:
        return 'universal'
    if operation in VALID_OPERATIONS:
        return operation
    return ''


def _current_operation() -> str:
    """Resolve a operação real antes de gerar o botão de download.

    BLINGFIX:
    - o wizard atual é universal e não deve cair visualmente como CADASTRO;
    - antes esta função só aceitava cadastro/estoque e fazia fallback para cadastro;
    - agora universal é operação válida e tem prioridade no single-page flow.
    """
    if bool(st.session_state.get('home_single_page_flow_active')):
        return 'universal'

    for key in (
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


def render_cadastro_download_step() -> None:
    operation = _current_operation()
    st.markdown('### Download da planilha final')
    st.caption('Baixe o arquivo final no mesmo modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(get_universal_final_df())
    if not valid_df(df_final):
        st.warning('A planilha final ainda não foi gerada. Volte ao preview.')
        return

    if render_row_count_blocker(df_final):
        return

    st.session_state['df_final_download_operation'] = operation
    download_final(df_final, operation, f'modelo_anexado_{operation}')


__all__ = ['render_cadastro_download_step']
