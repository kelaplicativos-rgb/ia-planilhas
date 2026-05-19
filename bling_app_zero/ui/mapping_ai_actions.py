from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.ai_mapping_assistant import (
    ai_mapping_enabled,
    ai_mapping_remaining_session_calls,
    apply_ai_mapping_assist,
    merge_ai_suggestions,
)
from bling_app_zero.ui.mapping_constants import CADASTRO_MAPPING_CONFIRMED_KEY, CADASTRO_MAPPING_SIGNATURE_KEY
from bling_app_zero.ui.mapping_widget_state import clear_mapping_widgets

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_ai_actions.py'


def _status_key(mapping_key: str) -> str:
    return f'{mapping_key}_ai_last_status'


def _render_last_ai_status(mapping_key: str) -> None:
    status = str(st.session_state.get(_status_key(mapping_key), '') or '')
    if not status:
        return
    if status == 'inactive':
        st.warning('IA Real não configurada. Configure a chave OpenAI para usar esta ajuda.')
        return
    if status == 'limit':
        st.warning('Limite de uso da IA Real nesta sessão atingido.')
        return
    if status == 'no_safe_changes':
        st.info('A IA Real analisou os produtos, mas não encontrou ligações seguras para aplicar.')
        return
    if status.startswith('applied:'):
        amount = status.split(':', 1)[1] or '0'
        st.success(f'IA Real aplicou {amount} sugestão(ões). Confira antes de continuar.')


def apply_ai_to_session_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> None:
    """Executa mapeamento inteligente com IA Real.

    A IA lê nomes das colunas e amostras reais dos produtos. Ela só aplica
    ligações aceitas pela validação local e sempre exige conferência do usuário.
    """
    status_key = _status_key(mapping_key)

    if not ai_mapping_enabled():
        st.session_state[status_key] = 'inactive'
        return

    if ai_mapping_remaining_session_calls() <= 0:
        st.session_state[status_key] = 'limit'
        return

    with st.spinner('IA Real lendo os produtos e sugerindo colunas...'):
        result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=False)

    if not result.enabled:
        st.session_state[status_key] = 'inactive'
        return

    if result.applied <= 0:
        st.session_state[status_key] = 'no_safe_changes'
        return

    st.session_state[mapping_key] = merge_ai_suggestions(current_mapping, result)
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    clear_mapping_widgets(mapping_key)
    st.session_state.pop(f'{mapping_key}_order', None)
    st.session_state[status_key] = f'applied:{result.applied}'
    st.rerun()


def render_ai_button(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
    label: str = '🤖 Usar IA Real para ligar colunas',
) -> None:
    """Mostra a ajuda da IA Real de forma explícita e compreensível."""
    with st.container(border=True):
        st.markdown('#### Ajuda da IA Real')
        st.caption('A IA lê os produtos da planilha e tenta ligar as colunas certas. Nada é definitivo: confira antes de continuar.')

        if not ai_mapping_enabled():
            st.warning('IA Real não configurada. O mapeamento manual continua disponível.')
            return

        remaining = ai_mapping_remaining_session_calls()
        st.caption(f'Usos restantes nesta sessão: {remaining}')
        if remaining <= 0:
            st.warning('Limite de uso da IA Real atingido nesta sessão.')
            return

        if st.button(label, use_container_width=True, key=f'{mapping_key}_ai'):
            apply_ai_to_session_mapping(df_source, target_columns, current_mapping, mapping_key)

        _render_last_ai_status(mapping_key)


__all__ = ['apply_ai_to_session_mapping', 'render_ai_button']
