from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.ai_mapping_assistant import ai_mapping_enabled, apply_ai_mapping_assist, merge_ai_suggestions
from bling_app_zero.ui.mapping_constants import CADASTRO_MAPPING_CONFIRMED_KEY, CADASTRO_MAPPING_SIGNATURE_KEY
from bling_app_zero.ui.mapping_widget_state import clear_mapping_widgets

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_ai_actions.py'


def apply_ai_to_session_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> None:
    """Aplica ajuda inteligente sem deixar balões permanentes na tela.

    BLINGFIX: dentro de Mapear campos, a ajuda deve ser discreta. A etapa
    completa de IA/Revisão fica separada depois do mapeamento. Por isso esta
    ação não renderiza st.info/st.success com blocos grandes abaixo do botão.
    """
    with st.spinner('Analisando campos...'):
        result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=True)

    if not result.enabled:
        st.session_state[f'{mapping_key}_ai_last_status'] = 'inactive'
        return

    if result.applied <= 0:
        st.session_state[f'{mapping_key}_ai_last_status'] = 'no_safe_changes'
        return

    st.session_state[mapping_key] = merge_ai_suggestions(current_mapping, result)
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    clear_mapping_widgets(mapping_key)
    st.session_state.pop(f'{mapping_key}_order', None)
    st.session_state[f'{mapping_key}_ai_last_status'] = f'applied:{result.applied}'
    st.rerun()


def render_ai_button(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
    label: str,
) -> None:
    """Mostra apenas um botão simples de ajuda inteligente."""
    if not ai_mapping_enabled():
        return

    button_label = '💡 Ajuda inteligente' if 'Ajuda' in str(label or '') else label
    if st.button(button_label, use_container_width=True, key=f'{mapping_key}_ai'):
        apply_ai_to_session_mapping(df_source, target_columns, current_mapping, mapping_key)


__all__ = ['apply_ai_to_session_mapping', 'render_ai_button']
