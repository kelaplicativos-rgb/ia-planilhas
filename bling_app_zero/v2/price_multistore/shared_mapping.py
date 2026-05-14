from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.mapping_constants import EMPTY_CHOOSE_OPTION
from bling_app_zero.ui.mapping_field_widget import render_mapping_select
from bling_app_zero.ui.mapping_widget_state import option_value
from bling_app_zero.v2.session_store import widget_key

RESPONSIBLE_FILE = 'bling_app_zero/v2/price_multistore/shared_mapping.py'
MAPPING_KEY = 'multistore_shared_mapping_v1'
MODEL_ID_TARGET = 'Identificador na planilha do Bling'
SOURCE_ID_TARGET = 'Identificador na origem'
SOURCE_COST_TARGET = 'Preço de custo da origem'


@dataclass(frozen=True)
class MultistoreMappingSelection:
    model_identifier_column: str
    source_identifier_column: str
    source_cost_column: str
    ready: bool
    errors: tuple[str, ...]


def _options(columns: Iterable[object]) -> list[str]:
    """Opções do mapeamento compartilhado para cruzamento multiloja.

    Aqui o componente visual é compartilhado com cadastro/estoque, mas estas três
    chaves são obrigatoriamente colunas reais: identificador Bling,
    identificador origem e preço de custo. Valor fixo/vazio continuam no
    mapeamento global, mas não servem para cruzar produtos.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for column in columns:
        text = str(column or '').strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return [EMPTY_CHOOSE_OPTION, *cleaned]


def _resolved_column(selected: str) -> str:
    return option_value(selected)


def _render_mapping_help() -> None:
    st.info(
        'Este fluxo usa o mesmo componente de mapeamento do cadastro/estoque, '
        'mas o cruzamento de preços exige colunas reais: uma coluna identificadora no Bling, '
        'uma coluna identificadora na origem e uma coluna de custo.'
    )


def render_multistore_shared_mapping(model_df: pd.DataFrame, source_df: pd.DataFrame) -> MultistoreMappingSelection:
    """Renderiza o mapeamento compartilhado do fluxo de preços multiloja."""
    model = model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame()
    source = source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) else pd.DataFrame()

    st.markdown('### Etapa 4 · Mapeamento compartilhado')
    _render_mapping_help()

    if model.empty or source.empty:
        return MultistoreMappingSelection('', '', '', False, ('Carregue a planilha do Bling e a origem de custo antes do mapeamento.',))

    with st.container(border=True):
        st.caption('1) Qual coluna da planilha do Bling identifica o produto/anúncio?')
        selected_model, _ = render_mapping_select(
            model,
            MODEL_ID_TARGET,
            0,
            str(st.session_state.get(widget_key('multistore_model_identifier_column'), '') or ''),
            MAPPING_KEY,
            _options(model.columns),
        )
        model_identifier = _resolved_column(selected_model)
        st.session_state[widget_key('multistore_model_identifier_column')] = model_identifier

    with st.container(border=True):
        st.caption('2) Qual coluna da origem/site corresponde ao mesmo produto?')
        selected_source_id, _ = render_mapping_select(
            source,
            SOURCE_ID_TARGET,
            1,
            str(st.session_state.get(widget_key('multistore_source_identifier_column'), '') or ''),
            MAPPING_KEY,
            _options(source.columns),
        )
        source_identifier = _resolved_column(selected_source_id)
        st.session_state[widget_key('multistore_source_identifier_column')] = source_identifier

    with st.container(border=True):
        st.caption('3) Qual coluna da origem/site contém o custo usado para recalcular o preço?')
        selected_cost, _ = render_mapping_select(
            source,
            SOURCE_COST_TARGET,
            2,
            str(st.session_state.get(widget_key('multistore_source_cost_column'), '') or ''),
            MAPPING_KEY,
            _options(source.columns),
        )
        source_cost = _resolved_column(selected_cost)
        st.session_state[widget_key('multistore_source_cost_column')] = source_cost

    errors: list[str] = []
    if not model_identifier or model_identifier not in model.columns:
        errors.append('Selecione uma coluna válida da planilha do Bling para identificar o produto/anúncio.')
    if not source_identifier or source_identifier not in source.columns:
        errors.append('Selecione uma coluna válida da origem/site para cruzar com o Bling.')
    if not source_cost or source_cost not in source.columns:
        errors.append('Selecione uma coluna válida da origem/site com o Preço de custo.')

    if errors:
        for error in errors:
            st.warning(error)
    else:
        st.success(f'Cruzamento definido: {model_identifier} ↔ {source_identifier} · custo: {source_cost}')

    return MultistoreMappingSelection(
        model_identifier_column=model_identifier,
        source_identifier_column=source_identifier,
        source_cost_column=source_cost,
        ready=not errors,
        errors=tuple(errors),
    )


__all__ = [
    'MODEL_ID_TARGET',
    'MAPPING_KEY',
    'MultistoreMappingSelection',
    'SOURCE_COST_TARGET',
    'SOURCE_ID_TARGET',
    'render_multistore_shared_mapping',
]
