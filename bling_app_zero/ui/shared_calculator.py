from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

import pandas as pd
import streamlit as st

UNIVERSAL_PRICE_COLUMN_KEY = 'mapeiaai_shared_price_column'


def parse_decimal(value: object) -> Decimal | None:
    text = str(value or '').strip()
    if not text:
        return None
    text = re.sub(r'[^0-9,.-]+', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def format_money(value: Decimal) -> str:
    return f'{value.quantize(Decimal("0.01"))}'.replace('.', ',')


def numeric_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    if not isinstance(df, pd.DataFrame):
        return columns
    for column in df.columns:
        sample = df[column].head(25).map(parse_decimal)
        if sample.notna().sum() >= max(1, min(3, len(sample))):
            columns.append(str(column))
    return columns


def apply_marketplace_calculation(
    source: pd.DataFrame,
    *,
    base_column: str,
    output_column: str,
    margin_percent: Decimal,
    fee_percent: Decimal,
    fixed_value: Decimal,
) -> pd.DataFrame:
    out = source.copy().fillna('')
    divisor = Decimal('1') - ((margin_percent + fee_percent) / Decimal('100'))
    if divisor <= 0:
        raise ValueError('Margem + taxas não pode chegar a 100% ou mais.')
    calculated: list[str] = []
    for value in out[base_column]:
        base = parse_decimal(value)
        calculated.append(format_money(((base or Decimal('0')) + fixed_value) / divisor))
    out[output_column] = calculated
    return out


def render_shared_calculator(source: pd.DataFrame, *, key_prefix: str = 'mapeiaai') -> pd.DataFrame:
    st.markdown('### Calculadora marketplace')
    with st.expander('Aplicar cálculo marketplace antes do mapeamento', expanded=False):
        columns = numeric_columns(source)
        if not columns:
            st.info('Não encontrei colunas numéricas suficientes para cálculo automático.')
            return source

        enabled = st.checkbox('Usar cálculo marketplace', value=False, key=f'{key_prefix}_use_price_calc')
        base_column = st.selectbox('Coluna base de preço/custo', columns, key=f'{key_prefix}_price_base_column')
        output_column = st.text_input('Nome da coluna calculada', value='Preço calculado marketplace', key=f'{key_prefix}_price_output_name')
        margin = Decimal(str(st.number_input('Margem (%)', min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key=f'{key_prefix}_margin') or 0))
        fee = Decimal(str(st.number_input('Taxas/marketplace (%)', min_value=0.0, max_value=1000.0, value=18.0, step=1.0, key=f'{key_prefix}_fee') or 0))
        fixed = Decimal(str(st.number_input('Valor fixo por item (R$)', min_value=0.0, max_value=100000.0, value=0.0, step=1.0, key=f'{key_prefix}_fixed') or 0))

        if not enabled:
            return source
        try:
            out = apply_marketplace_calculation(
                source,
                base_column=base_column,
                output_column=output_column,
                margin_percent=margin,
                fee_percent=fee,
                fixed_value=fixed,
            )
        except ValueError as exc:
            st.error(str(exc))
            return source
        st.session_state[UNIVERSAL_PRICE_COLUMN_KEY] = output_column
        st.success(f'Cálculo aplicado na coluna de origem: {output_column}')
        return out


__all__ = [
    'UNIVERSAL_PRICE_COLUMN_KEY',
    'apply_marketplace_calculation',
    'format_money',
    'numeric_columns',
    'parse_decimal',
    'render_shared_calculator',
]
