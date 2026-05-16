from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.engines.cadastro_engine import default_model as cadastro_default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model
from bling_app_zero.ui.estoque_wizard_state import stock_confidence, stock_mapping
from bling_app_zero.ui.mapping_cadastro_flow import render_manual_mapping
from bling_app_zero.ui.mapping_estoque_flow import render_manual_stock_mapping
from bling_app_zero.ui.mapping_review_panel import render_mapping_review_panel

EMPTY_OPTION = '(deixar vazio)'


def _model_columns(df_modelo: pd.DataFrame | None, operation: str) -> list[str]:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return [str(column) for column in df_modelo.columns]
    if operation == 'estoque':
        return [str(column) for column in estoque_default_model().columns]
    return [str(column) for column in cadastro_default_model().columns]


def render_shared_cadastro_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    render_manual_mapping(df_source, df_modelo)
    render_mapping_review_panel(
        operation='cadastro',
        mapping=st.session_state.get('mapping_cadastro'),
        confidence=st.session_state.get('mapping_confidence_cadastro'),
        df_source=df_source,
        target_columns=_model_columns(df_modelo, 'cadastro'),
    )


def render_shared_stock_mapping(
    df_source: pd.DataFrame,
    df_modelo_estoque: pd.DataFrame | None,
    deposito: str,
) -> None:
    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)
    render_mapping_review_panel(
        operation='estoque',
        mapping=stock_mapping(),
        confidence=stock_confidence(),
        df_source=df_source,
        target_columns=_model_columns(df_modelo_estoque, 'estoque'),
    )


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


def render_shared_contract_mapping(
    source: pd.DataFrame,
    target: pd.DataFrame,
    *,
    signature: str,
    mapping_state_key: str,
    engine_state_key: str,
    key_prefix: str = 'mapeiaai_shared',
) -> dict[str, str]:
    st.markdown('### Mapeamento compartilhado com faróis')
    st.caption('Cada coluna do contrato final aponta para uma coluna da origem. O que não existir fica vazio.')

    if mapping_state_key not in st.session_state:
        suggested, engine = suggest_shared_mapping(source, target, operation='universal')
        st.session_state[mapping_state_key] = suggested
        st.session_state[engine_state_key] = engine

    engine = str(st.session_state.get(engine_state_key) or 'local')
    st.caption('Motor de sugestão: OpenAI validada' if engine == 'openai_validated' else 'Motor de sugestão: local seguro')

    current = dict(st.session_state.get(mapping_state_key) or {})
    source_options = [EMPTY_OPTION] + [str(column) for column in source.columns]
    edited: dict[str, str] = {}
    rows: list[dict[str, str]] = []

    for index, target_column in enumerate(target.columns):
        target_name = str(target_column)
        current_value = current.get(target_name, '')
        default_index = source_options.index(current_value) if current_value in source_options else 0
        selected = st.selectbox(
            target_name,
            source_options,
            index=default_index,
            key=mapping_widget_key(key_prefix, signature, index, target_name),
        )
        selected_value = '' if selected == EMPTY_OPTION else selected
        edited[target_name] = selected_value
        rows.append(
            {
                'Farol': confidence_flag(target_name, selected_value, source),
                'Contrato final': target_name,
                'Origem usada': selected_value or '(vazio)',
            }
        )

    st.session_state[mapping_state_key] = edited
    with st.expander('Resumo dos faróis do mapeamento', expanded=True):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=260)
    return edited


def clear_shared_mapping_widgets(key_prefix: str = 'mapeiaai_shared') -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f'{key_prefix}_map_'):
            st.session_state.pop(key, None)


__all__ = [
    'EMPTY_OPTION',
    'clear_shared_mapping_widgets',
    'confidence_flag',
    'mapping_widget_key',
    'render_shared_cadastro_mapping',
    'render_shared_contract_mapping',
    'render_shared_stock_mapping',
    'short_hash',
    'suggest_shared_mapping',
]
