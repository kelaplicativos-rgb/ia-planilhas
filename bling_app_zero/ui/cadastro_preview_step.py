from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.flow_spine_output import output_diagnostics, output_is_api, output_operation, preview_caption, preview_title
from bling_app_zero.ui.cadastro_wizard_state import (
    get_universal_final_df,
    render_row_count_blocker,
    set_universal_final_df,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_preview_step.py'
SMARTCORE_PREVIEW_KEY = 'universal_preview_report'


def _current_operation() -> str:
    operation = normalize_contract_operation(output_operation())
    return operation or 'universal'


def _context_final_df() -> pd.DataFrame | None:
    for key in (
        'df_final_universal',
        'df_final_cadastro',
        'df_final_cadastro_preview_rules_applied',
        'df_final_download_snapshot',
    ):
        df = st.session_state.get(key)
        if valid_df(df):
            return df.copy().fillna('')
    legacy = get_universal_final_df()
    return legacy.copy().fillna('') if valid_df(legacy) else None


def _store_context_preview(df_preview: pd.DataFrame, operation: str) -> None:
    st.session_state['df_final_universal'] = df_preview.copy()
    set_universal_final_df(df_preview)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview.copy()
    st.session_state['df_final_preview_operation'] = 'universal'
    st.session_state['flow_spine_preview_ready'] = True
    st.session_state[SMARTCORE_PREVIEW_KEY] = {
        'operation': 'universal',
        'rows': int(len(df_preview)),
        'columns': int(len(df_preview.columns)),
        'flow_spine': output_diagnostics(),
    }


def _final_preview_df(df_final: pd.DataFrame, operation: str) -> pd.DataFrame:
    # Prévia universal: não transforma, não aplica contrato interno e não altera valores.
    return df_final.copy().fillna('') if isinstance(df_final, pd.DataFrame) else pd.DataFrame()


def render_cadastro_preview_step() -> None:
    operation = _current_operation()
    st.markdown(f'### {preview_title()}')
    st.caption(preview_caption())
    df_final = _context_final_df()
    if not valid_df(df_final):
        st.warning('A prévia final ainda não foi gerada. Volte para o mapeamento e confirme os campos.')
        return
    df_preview = _final_preview_df(df_final, operation)
    _store_context_preview(df_preview, operation)
    if not output_is_api() and render_row_count_blocker(df_preview):
        return
    preview_df('Resultado final preenchido', df_preview)


__all__ = ['render_cadastro_preview_step']
