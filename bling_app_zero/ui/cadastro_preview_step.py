from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_preview_step.py'
VALID_OPERATIONS = {'cadastro', 'estoque'}


def _current_operation() -> str:
    """Resolve a operação real do fluxo antes de aplicar regras do preview.

    BLINGFIX #loop:
    - o preview estava sempre usando `operation='cadastro'`;
    - quando o usuário estava no fluxo de estoque, as regras e validações podiam
      rodar no escopo errado;
    - agora a operação é lida das mesmas chaves usadas pelo wizard/site, com
      fallback seguro para cadastro.
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


def _final_preview_df(df_final: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica no preview a mesma blindagem usada na planilha final."""
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation=operation)
    return enforce_cadastro_model_columns(safe)


def render_cadastro_preview_step() -> None:
    operation = _current_operation()
    st.markdown('### Preview da planilha final')
    st.caption('Confira se o arquivo final segue o modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    df_preview = _final_preview_df(df_final, operation)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview
    st.session_state['df_final_preview_operation'] = operation

    if render_row_count_blocker(df_preview):
        return

    preview_df('Planilha final', df_preview)


__all__ = ['render_cadastro_preview_step']
