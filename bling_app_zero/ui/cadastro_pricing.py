from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.core.pricing import detect_discount_percent
from bling_app_zero.ui.home_shared import df_signature, load_apply_pricing, preview_df

DEFAULT_PROFIT_PERCENT = 50.0

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]


def apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in PRICE_TARGET_ALIASES:
        out[column] = calculated_values
    return out


def best_cost_column(columns: list[str]) -> int:
    preferred_terms = ['custo', 'preço custo', 'preco custo', 'valor produto', 'valor', 'preço', 'preco', 'price']
    lower_columns = [column.lower() for column in columns]
    for term in preferred_terms:
        for index, column in enumerate(lower_columns):
            if term in column:
                return index
    return 0


def sync_detected_discount(df_origem: pd.DataFrame, signature: str) -> float:
    detected = float(detect_discount_percent(df_origem) or 0.0)
    previous_signature = st.session_state.get('cadastro_precificacao_signature')
    if previous_signature != signature:
        st.session_state['cadastro_precificacao_signature'] = signature
        st.session_state['cadastro_desconto_comissao'] = detected
    if 'cadastro_desconto_comissao' not in st.session_state:
        st.session_state['cadastro_desconto_comissao'] = detected
    return detected


def _show_first_row_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    if selected_column not in df_source.columns or df_source.empty:
        return
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    if len(text) > 160:
        text = text[:160] + '...'
    if not text:
        return
    safe_text = html.escape(text)
    st.markdown(
        f"<div style='font-size:12px; color:#118a32; margin-top:2px; margin-bottom:4px; font-weight:750; overflow-wrap:anywhere;'>{safe_text}</div>",
        unsafe_allow_html=True,
    )


def render_cadastro_pricing(df_origem: pd.DataFrame) -> pd.DataFrame:
    usar_preco = st.checkbox('Aplicar calculadora de preço', value=False)
    if not usar_preco:
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_cadastro_precificada', None)
        return df_origem

    apply_pricing = load_apply_pricing()
    colunas = [str(c) for c in df_origem.columns]
    origem_signature = df_signature(df_origem)
    desconto_detectado = sync_detected_discount(df_origem, origem_signature)
    coluna_custo = st.selectbox(
        'Coluna de custo/preço base',
        colunas,
        index=best_cost_column(colunas),
        key=f'cadastro_coluna_custo_{origem_signature}',
    )
    _show_first_row_preview(df_origem, coluna_custo)
    if desconto_detectado > 0:
        st.info(f'Desconto/comissão detectado: {desconto_detectado:.2f}%')

    c1, c2, c3, c4, c5 = st.columns(5)
    margem = c1.number_input('Lucro %', min_value=0.0, value=DEFAULT_PROFIT_PERCENT, step=1.0, key=f'cadastro_margem_{origem_signature}')
    imposto = c2.number_input('Impostos %', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_imposto_{origem_signature}')
    taxa = c3.number_input('Taxas %', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_taxa_{origem_signature}')
    desconto = c4.number_input('Desconto %', min_value=0.0, step=1.0, key='cadastro_desconto_comissao')
    fixo = c5.number_input('Fixo R$', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_fixo_{origem_signature}')

    df_precificado = apply_pricing(df_origem, coluna_custo, 'Preço de venda', margem, imposto, taxa, fixo, desconto)
    df_precificado = apply_calculated_price_aliases(df_precificado, 'Preço de venda')
    st.session_state['cadastro_preco_calculado_ativo'] = True
    st.session_state['df_origem_cadastro_precificada'] = df_precificado
    with st.expander('Ver preço calculado', expanded=False):
        preview_df('Origem com preço calculado', df_precificado)
    return df_precificado
