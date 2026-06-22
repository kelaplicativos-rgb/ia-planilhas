from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.ui.mapping_cadastro_flow import render_manual_mapping
from bling_app_zero.ui.mapping_estoque_flow import render_manual_stock_mapping

EMPTY_OPTION = '(deixar vazio)'


def render_shared_cadastro_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    """Renderiza somente o mapeamento manual.

    Regra de UX: qualquer painel de IA/revisão deve aparecer somente depois de
    Mapear campos e antes do Preview da planilha final.
    """
    render_manual_mapping(df_source, df_modelo)


def render_shared_stock_mapping(
    df_source: pd.DataFrame,
    df_modelo_estoque: pd.DataFrame | None,
    deposito: str,
) -> None:
    """Renderiza somente o mapeamento manual de estoque."""
    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)


def short_hash(value: str, size: int = 8) -> str:
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()[:size]


def mapping_widget_key(key_prefix: str, signature: str, index: int, target_name: str) -> str:
    return f'{key_prefix}_map_{index}_{short_hash(signature + target_name)}'


def confidence_flag(target: str, source_column: str, source: pd.DataFrame) -> str:
    if not source_column:
        return '🔴 vazio'
    target_key = re.sub(r'[^a-z0-9]+', '', str(target or '').lower())
    source_key = re.sub(r'[^a-z0-9]+', '', str(source_column or '').lower())
    if target_key and (target_key == source_key or target_key in source_key or source_key in target_key):
        return '🟢 alto'
    if source_column in source.columns and source[source_column].astype(str).str.strip().ne('').any():
        return '🟡 revisar'
    return '🔴 vazio'


def suggest_shared_mapping(source: pd.DataFrame, target: pd.DataFrame, *, operation: str = 'universal') -> tuple[dict[str, str], str]:
    result = suggest_mapping_with_openai(source, target, operation=operation)
    data = result.data if isinstance(result.data, dict) else {}
    mapping = data.get('mapping')
    engine = str(data.get('engine') or 'local')
    safe_mapping = {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}
    return safe_mapping, engine


def blank_shared_mapping(target: pd.DataFrame) -> dict[str, str]:
    return {str(column): '' for column in getattr(target, 'columns', [])}


def _sample_values(source: pd.DataFrame, source_column: str, limit: int = 3) -> list[str]:
    if not isinstance(source, pd.DataFrame) or not source_column or source_column not in source.columns:
        return []
    values: list[str] = []
    try:
        for value in source[source_column].dropna().astype(str).head(limit * 4):
            text = str(value or '').strip()
            if text and text.lower() not in {'nan', 'none', 'null'} and text not in values:
                values.append(text)
            if len(values) >= limit:
                break
    except Exception:
        return []
    return values


def _render_mapping_preview(target_name: str, selected_value: str, source: pd.DataFrame) -> None:
    """Mostra o contrato final e a prévia do dado que entrará naquele campo."""
    flag = confidence_flag(target_name, selected_value, source)
    if not selected_value:
        st.caption(f'{flag} Campo do modelo: **{target_name}** → ficará vazio no download final.')
        return

    samples = _sample_values(source, selected_value)
    if samples:
        sample_text = ' | '.join(samples)
        st.caption(f'{flag} Campo do modelo: **{target_name}** ← origem **{selected_value}**. Prévia: {sample_text}')
    else:
        st.caption(f'{flag} Campo do modelo: **{target_name}** ← origem **{selected_value}**. Prévia indisponível ou coluna vazia.')


def render_shared_contract_mapping(
    source: pd.DataFrame,
    target: pd.DataFrame,
    *,
    signature: str,
    mapping_state_key: str,
    engine_state_key: str,
    key_prefix: str = 'mapeiaai_shared',
    ai_enabled: bool = True,
) -> dict[str, str]:
    st.markdown('### Mapeamento')
    if ai_enabled:
        st.caption('IA opcional ligada: o sistema sugere os campos, mas você revisa e pode alterar tudo antes do preview final.')
    else:
        st.caption('IA desligada: os campos começam vazios e somente escolhas manuais serão usadas no download.')

    if mapping_state_key not in st.session_state:
        if ai_enabled:
            suggested, engine = suggest_shared_mapping(source, target, operation='universal')
        else:
            suggested, engine = blank_shared_mapping(target), 'manual_sem_ia'
        st.session_state[mapping_state_key] = suggested
        st.session_state[engine_state_key] = engine

    if not ai_enabled and str(st.session_state.get(engine_state_key) or '') != 'manual_sem_ia':
        st.session_state[mapping_state_key] = blank_shared_mapping(target)
        st.session_state[engine_state_key] = 'manual_sem_ia'

    engine = str(st.session_state.get(engine_state_key) or 'local')
    if engine == 'openai_validated':
        st.caption('Motor de sugestão: OpenAI validada')
    elif engine == 'manual_sem_ia':
        st.caption('Motor de sugestão: manual sem IA')
    else:
        st.caption('Motor de sugestão: local seguro')

    current = dict(st.session_state.get(mapping_state_key) or {})
    source_options = [EMPTY_OPTION] + [str(column) for column in source.columns]
    edited: dict[str, str] = {}
    rows: list[dict[str, str]] = []

    st.caption('Para cada campo do modelo abaixo, escolha qual coluna da origem vai preencher esse campo. A prévia aparece logo abaixo de cada seleção.')

    for index, target_column in enumerate(target.columns):
        target_name = str(target_column)
        current_value = current.get(target_name, '')
        default_index = source_options.index(current_value) if current_value in source_options else 0

        st.markdown(f'**Campo do modelo:** `{target_name}`')
        selected = st.selectbox(
            f'Origem que vai preencher “{target_name}”',
            source_options,
            index=default_index,
            key=mapping_widget_key(key_prefix, signature, index, target_name),
        )
        selected_value = '' if selected == EMPTY_OPTION else selected
        edited[target_name] = selected_value
        _render_mapping_preview(target_name, selected_value, source)
        rows.append(
            {
                'Farol': confidence_flag(target_name, selected_value, source),
                'Contrato final': target_name,
                'Origem usada': selected_value or '(vazio)',
            }
        )

    st.session_state[mapping_state_key] = edited
    with st.expander('Resumo dos faróis do mapeamento', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=260)
    return edited


def clear_shared_mapping_widgets(key_prefix: str = 'mapeiaai_shared') -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f'{key_prefix}_map_'):
            st.session_state.pop(key, None)


__all__ = [
    'EMPTY_OPTION',
    'blank_shared_mapping',
    'clear_shared_mapping_widgets',
    'confidence_flag',
    'mapping_widget_key',
    'render_shared_cadastro_mapping',
    'render_shared_contract_mapping',
    'render_shared_stock_mapping',
    'short_hash',
    'suggest_shared_mapping',
]
