from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.ai_mapping_assistant import ai_mapping_enabled, apply_ai_mapping_assist, merge_ai_suggestions
from bling_app_zero.ui.mapping_constants import CADASTRO_MAPPING_CONFIRMED_KEY, CADASTRO_MAPPING_SIGNATURE_KEY
from bling_app_zero.ui.mapping_widget_state import clear_mapping_widgets


def apply_ai_to_session_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> None:
    result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=True)
    if not result.enabled:
        st.warning('Assistência com IA não configurada. Para usar, adicione OPENAI_API_KEY nos secrets do Streamlit.')
        return
    if result.applied <= 0:
        st.info('A IA não encontrou ajustes seguros para aplicar agora.')
        return

    st.session_state[mapping_key] = merge_ai_suggestions(current_mapping, result)
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    clear_mapping_widgets(mapping_key)
    st.session_state.pop(f'{mapping_key}_order', None)
    st.success(f'IA ajustou {result.applied} campo(s) com segurança.')
    st.rerun()


def render_ai_button(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
    label: str,
) -> None:
    if not ai_mapping_enabled():
        st.caption('IA opcional inativa. Configure OPENAI_API_KEY para receber ajuda nos campos em dúvida.')
        return
    if st.button(label, use_container_width=True, key=f'{mapping_key}_ai'):
        apply_ai_to_session_mapping(df_source, target_columns, current_mapping, mapping_key)


__all__ = ['apply_ai_to_session_mapping', 'render_ai_button']
