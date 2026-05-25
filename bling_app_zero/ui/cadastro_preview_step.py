from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    get_universal_final_df,
    render_row_count_blocker,
    set_universal_final_df,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_preview_step.py'
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
    """Resolve a operação real do fluxo antes de aplicar regras do preview.

    BLINGFIX:
    - o wizard atual pode operar como universal/modelo final;
    - antes o preview aceitava só cadastro/estoque e fazia fallback para cadastro;
    - agora universal é válido e tem prioridade quando o single-page flow está ativo.
    """
    if bool(st.session_state.get('home_single_page_flow_active')):
        return 'universal'

    for key in (
        'df_final_preview_operation',
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


def _final_preview_df(df_final: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica no preview a mesma blindagem usada na planilha final."""
    safe_operation = operation if operation in VALID_OPERATIONS else 'universal'
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation=safe_operation)
    fixed = enforce_cadastro_model_columns(safe)
    return fixed if isinstance(fixed, pd.DataFrame) else safe


def render_cadastro_preview_step() -> None:
    operation = _current_operation()
    st.markdown('### Preview do modelo final')
    st.caption('Confira se o arquivo final segue o modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(get_universal_final_df())

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    df_preview = _final_preview_df(df_final, operation)
    set_universal_final_df(df_preview)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview
    st.session_state['df_final_preview_operation'] = operation

    if render_row_count_blocker(df_preview):
        return

    preview_df('Modelo final preenchido', df_preview)


__all__ = ['render_cadastro_preview_step']
