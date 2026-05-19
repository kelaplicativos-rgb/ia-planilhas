from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.bling_links_panel import render_bling_links_panel
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_download_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque'}


def _current_operation() -> str:
    """Resolve a operação real antes de gerar o botão de download.

    BLINGFIX #loop:
    - antes o download era chamado com `operation='modelo'`;
    - isso podia gerar nome genérico, validação errada e preservar estado errado;
    - agora o download recebe `cadastro` ou `estoque`, conforme a sessão atual.
    """
    for key in (
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
        'home_slim_flow_operation',
        'home_detected_operation',
    ):
        operation = str(st.session_state.get(key) or '').strip().lower()
        if operation in VALID_OPERATIONS:
            return operation

    try:
        operation = str(st.query_params.get('operacao', '') or '').strip().lower()
        if operation in VALID_OPERATIONS:
            return operation
    except Exception:
        pass

    return 'cadastro'


def render_cadastro_download_step() -> None:
    operation = _current_operation()
    st.markdown('### Download da planilha final')
    st.caption('Baixe o arquivo final no mesmo modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('A planilha final ainda não foi gerada. Volte ao preview.')
        return

    if render_row_count_blocker(df_final):
        return

    st.session_state['df_final_download_operation'] = operation
    download_final(df_final, operation, f'modelo_anexado_{operation}')
    st.divider()
    render_bling_links_panel()


__all__ = ['render_cadastro_download_step']
