from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ai_tools import build_blingbrain_response
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home_shared import df_signature


DEFAULT_PROMPTS = {
    'cadastro': 'Revisar descrições, títulos, GTIN, NCM e campos vazios antes do download final.',
    'estoque': 'Conferir produto, depósito, quantidade, códigos e campos vazios antes do download final.',
}

OPERATION_LABELS = {
    'cadastro': 'CADASTRO',
    'estoque': 'ESTOQUE',
}


def _operation_label(operation: str) -> str:
    return OPERATION_LABELS.get(str(operation or '').strip().lower(), 'ARQUIVO')


def _state_key(operation: str, signature: str, suffix: str) -> str:
    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    return f'preview_ai_{op}_{signature}_{suffix}'


def _column_summary(df: pd.DataFrame) -> str:
    columns = [str(column) for column in df.columns]
    if len(columns) <= 12:
        return ', '.join(columns)
    return ', '.join(columns[:12]) + f' ... +{len(columns) - 12} coluna(s)'


def _empty_cells_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return 'sem dados'
    sample = df.head(200).copy()
    empty_counts: list[str] = []
    for column in sample.columns:
        series = sample[column]
        normalized = series.fillna('').astype(str).str.strip()
        count = int(normalized.isin(['', 'nan', 'None', 'none', '<NA>']).sum())
        if count > 0:
            empty_counts.append(f'{column}: {count}')
    if not empty_counts:
        return 'nenhum vazio relevante na amostra'
    return '; '.join(empty_counts[:8])


def _build_context_prompt(df: pd.DataFrame, operation: str, user_prompt: str) -> str:
    label = _operation_label(operation)
    return (
        f'{user_prompt}\n\n'
        f'Contexto do preview final de {label}: '
        f'{len(df)} linha(s), {len(df.columns)} coluna(s). '
        f'Colunas: {_column_summary(df)}. '
        f'Campos vazios na amostra: {_empty_cells_summary(df)}.'
    )


def _render_ai_result(result: Any) -> None:
    st.success(result.title)
    st.caption(result.safety)
    st.markdown('**Plano da IA para este preview:**')
    for step in result.steps:
        st.markdown(f'- {step}')


def render_preview_ai_actions(df_final: pd.DataFrame | None, operation: str) -> None:
    """Botão de IA no preview final.

    A primeira versão é segura: ela analisa o contexto do preview final e mostra
    o plano de revisão, sem alterar o DataFrame nem o CSV automaticamente.
    """
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return

    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    label = _operation_label(op)
    signature = df_signature(df_final)
    prompt_key = _state_key(op, signature, 'prompt')
    result_key = _state_key(op, signature, 'result')

    st.markdown(
        """
        <div class="bling-inline-card">
            <div class="bling-flow-card-kicker">IA no preview final</div>
            <div class="bling-flow-card-title">Executar conferência com IA</div>
            <p class="bling-flow-card-text">Use a IA para revisar o arquivo final antes do download, sem alterar o CSV automaticamente.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_prompt = DEFAULT_PROMPTS.get(op, 'Conferir o arquivo final antes do download.')
    prompt = st.text_area(
        f'O que a IA deve conferir no preview de {label}?',
        value=st.session_state.get(prompt_key, default_prompt),
        key=prompt_key,
        height=78,
        help='A IA gera uma conferência segura. O CSV só será alterado quando existir uma ação confirmada pelo usuário.',
    )

    if st.button(f'🤖 Executar IA no preview final de {label}', use_container_width=True, key=_state_key(op, signature, 'run')):
        context_prompt = _build_context_prompt(df_final, op, prompt)
        st.session_state[result_key] = build_blingbrain_response(context_prompt, etapa='preview final', operacao=op)
        add_debug(f'IA executada no preview final de {label}.', origin='PREVIEW_IA', level='INFO')
        st.rerun()

    result = st.session_state.get(result_key)
    if result is not None:
        with st.expander(f'🤖 Resultado da IA · Preview final de {label}', expanded=True):
            _render_ai_result(result)


__all__ = ['render_preview_ai_actions']
