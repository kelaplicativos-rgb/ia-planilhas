from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import super_auto_map_columns
from bling_app_zero.core.pricing import detect_discount_percent
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.cadastro_engine import default_model as cadastro_default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model
from bling_app_zero.ui.cadastro_pricing import apply_calculated_price_aliases, best_cost_column
from bling_app_zero.ui.home_shared import df_signature, load_apply_pricing, preview_df

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]


def sync_detected_discount(df_origem: pd.DataFrame, signature: str) -> float:
    detected = float(detect_discount_percent(df_origem) or 0.0)
    previous_signature = st.session_state.get('cadastro_precificacao_signature')
    if previous_signature != signature:
        st.session_state['cadastro_precificacao_signature'] = signature
        st.session_state['cadastro_desconto_comissao'] = detected
    if 'cadastro_desconto_comissao' not in st.session_state:
        st.session_state['cadastro_desconto_comissao'] = detected
    return detected


def cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return cadastro_default_model()


def estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return estoque_default_model()


def default_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def first_row_preview(df_source: pd.DataFrame, selected_column: str) -> str:
    if not selected_column or selected_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    if len(text) > 180:
        text = text[:180] + '...'
    return text


def show_first_row_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    text = first_row_preview(df_source, selected_column)
    if not text:
        return
    safe_text = html.escape(text)
    st.markdown(f'<div class="bling-inline-preview">{safe_text}</div>', unsafe_allow_html=True)


def force_price_suggestion(target: str, source_columns: list[str], suggested: str) -> str:
    if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
        return 'Preço de venda'
    return suggested


def fill_deposito_manual(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if not deposito:
        return out
    for column in out.columns:
        if 'deposito' in normalize_key(column):
            out[column] = deposito
    return out


def apply_pricing_ui(df_origem: pd.DataFrame, key_prefix: str, preview_title: str) -> pd.DataFrame:
    apply_pricing = load_apply_pricing()
    colunas = [str(column) for column in df_origem.columns]
    origem_signature = df_signature(df_origem)
    desconto_detectado = sync_detected_discount(df_origem, f'{key_prefix}:{origem_signature}')

    coluna_custo = st.selectbox(
        'Coluna de custo/preço base',
        colunas,
        index=best_cost_column(colunas),
        key=f'{key_prefix}_coluna_custo_{origem_signature}',
    )
    show_first_row_preview(df_origem, coluna_custo)

    if desconto_detectado > 0:
        st.info(f'Comissão/marketplace detectado e aplicado como padrão: {desconto_detectado:.2f}%')

    c1, c2, c3, c4, c5 = st.columns(5)
    margem = c1.number_input('Lucro desejado %', min_value=0.0, value=30.0, step=1.0, key=f'{key_prefix}_margem_{origem_signature}')
    imposto = c2.number_input('Impostos %', min_value=0.0, value=0.0, step=1.0, key=f'{key_prefix}_imposto_{origem_signature}')
    taxa = c3.number_input('Taxas da venda %', min_value=0.0, value=0.0, step=1.0, key=f'{key_prefix}_taxa_{origem_signature}')
    comissao = c4.number_input('Comissão / marketplace %', min_value=0.0, step=1.0, key='cadastro_desconto_comissao')
    fixo = c5.number_input('Custo fixo R$', min_value=0.0, value=0.0, step=1.0, key=f'{key_prefix}_fixo_{origem_signature}')

    df_precificado = apply_pricing(df_origem, coluna_custo, 'Preço de venda', margem, imposto, taxa, fixo, comissao)
    df_precificado = apply_calculated_price_aliases(df_precificado, 'Preço de venda')
    preview_df(preview_title, df_precificado)
    return df_precificado


def build_manual_mapping_result(
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    mapping_key_prefix: str,
    title: str,
    caption: str,
    force_price: bool = True,
) -> tuple[pd.DataFrame, dict[str, str]]:
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [''] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    mapping_key = f'{mapping_key_prefix}_{signature}'

    if mapping_key not in st.session_state:
        auto_mapping = super_auto_map_columns(df_source, model)
        if force_price:
            for target, selected in list(auto_mapping.items()):
                auto_mapping[target] = force_price_suggestion(target, source_columns, selected)
        st.session_state[mapping_key] = auto_mapping

    st.markdown(title)
    st.caption(caption)
    preview_df('Origem para conferir', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    edited_mapping: dict[str, str] = {}
    for target in target_columns:
        suggested = current_mapping.get(target, '')
        widget_key = f'{mapping_key}_{target}'
        if widget_key in st.session_state:
            suggested = st.session_state.get(widget_key, suggested)
        selected = st.selectbox(target, options, index=default_index(options, suggested), key=widget_key, help=f'Campo de destino no Bling: {target}')
        show_first_row_preview(df_source, selected)
        edited_mapping[target] = selected

    st.session_state[mapping_key] = edited_mapping
    df_preview_manual = sanitize_for_bling(apply_mapping(df_source, model, edited_mapping))

    used_values = [value for value in edited_mapping.values() if value]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna da origem foi usada mais de uma vez: ' + ', '.join(duplicated))

    return df_preview_manual, edited_mapping
