from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

import pandas as pd
import streamlit as st

UNIVERSAL_PRICE_COLUMN_KEY = 'mapeiaai_shared_price_column'
UNIVERSAL_PRICE_TARGET_COLUMN_KEY = 'mapeiaai_shared_price_target_column'
UNIVERSAL_PRICE_BASE_COLUMN_KEY = 'mapeiaai_shared_price_base_column'
UNIVERSAL_PRICE_AUTOMAP_KEY = 'mapeiaai_shared_price_automap_enabled'
UNIVERSAL_MODEL_STATE_CANDIDATES = (
    'mapeiaai_universal_model_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
)
PRICE_TARGET_TERMS = (
    'preco', 'preço', 'valor', 'venda', 'unitario', 'unitário', 'marketplace',
    'preco venda', 'preço venda', 'valor venda', 'preço de venda', 'preco de venda',
)
COST_SOURCE_TERMS = (
    'custo', 'preco custo', 'preço custo', 'valor custo', 'compra', 'fornecedor', 'cost',
)
SALE_SOURCE_TERMS = (
    'preco', 'preço', 'valor', 'venda', 'price', 'unitario', 'unitário',
)
TECHNICAL_NON_TARGET_TERMS = (
    'arquivo', 'arquivo zip', 'arquivo no zip', 'status', 'conteudo extraido',
    'conteúdo extraído', 'texto extraido', 'texto extraído', 'tamanho bytes',
)


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


def _norm(value: Any) -> str:
    text = str(value or '').casefold()
    text = text.replace('ç', 'c').replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i').replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _has_any(value: Any, terms: tuple[str, ...]) -> bool:
    normalized = _norm(value)
    return any(_norm(term) in normalized for term in terms)


def _is_technical_non_target_column(column: Any) -> bool:
    normalized = _norm(column)
    return normalized in {_norm(term) for term in TECHNICAL_NON_TARGET_TERMS}


def numeric_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    if not isinstance(df, pd.DataFrame):
        return columns
    for column in df.columns:
        sample = df[column].head(25).map(parse_decimal)
        if sample.notna().sum() >= max(1, min(3, len(sample))):
            columns.append(str(column))
    return columns


def _score_base_price_column(column: str) -> int:
    normalized = _norm(column)
    score = 0
    if _has_any(normalized, COST_SOURCE_TERMS):
        score += 70
    if _has_any(normalized, SALE_SOURCE_TERMS):
        score += 35
    if 'promoc' in normalized:
        score -= 15
    if any(term in normalized for term in ('estoque', 'saldo', 'quantidade', 'qtd')):
        score -= 80
    return score


def default_base_price_column(source: pd.DataFrame) -> str:
    columns = numeric_columns(source)
    if not columns:
        return ''
    ranked = sorted(columns, key=lambda column: (_score_base_price_column(column), -columns.index(column)), reverse=True)
    return ranked[0]


def _model_from_session() -> pd.DataFrame | None:
    for key in UNIVERSAL_MODEL_STATE_CANDIDATES:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns):
            return value.copy().fillna('')
    return None


def price_target_columns(model: pd.DataFrame | None) -> list[str]:
    if not isinstance(model, pd.DataFrame) or not len(model.columns):
        return []
    return [str(column) for column in model.columns if _has_any(column, PRICE_TARGET_TERMS) and not _is_technical_non_target_column(column)]


def manual_target_columns(model: pd.DataFrame | None) -> list[str]:
    if not isinstance(model, pd.DataFrame) or not len(model.columns):
        return []
    return [str(column) for column in model.columns if not _is_technical_non_target_column(column)]


def default_price_target_column(model: pd.DataFrame | None) -> str:
    targets = price_target_columns(model)
    if not targets:
        return ''

    def score(column: str) -> int:
        normalized = _norm(column)
        value = 0
        if 'venda' in normalized:
            value += 80
        if 'preco' in normalized or 'valor' in normalized:
            value += 60
        if 'unitario' in normalized:
            value += 20
        if 'custo' in normalized or 'compra' in normalized:
            value -= 80
        if 'promoc' in normalized:
            value += 15
        return value

    ranked = sorted(targets, key=lambda column: (score(column), -targets.index(column)), reverse=True)
    return ranked[0]


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


def render_shared_calculator(
    source: pd.DataFrame,
    *,
    model: pd.DataFrame | None = None,
    key_prefix: str = 'mapeiaai',
    force_enabled: bool | None = None,
) -> pd.DataFrame:
    st.markdown('### Calculadora marketplace')
    expanded = bool(force_enabled)
    with st.expander('Aplicar cálculo marketplace antes do mapeamento', expanded=expanded):
        columns = numeric_columns(source)
        if not columns:
            st.info('Não encontrei colunas numéricas suficientes para cálculo automático.')
            return source

        if force_enabled is None:
            enabled = st.checkbox('Usar cálculo marketplace', value=False, key=f'{key_prefix}_use_price_calc')
        else:
            enabled = bool(force_enabled)
            st.caption('Cálculo marketplace ligado pelo toggle principal do fluxo.')

        default_base = default_base_price_column(source)
        base_index = columns.index(default_base) if default_base in columns else 0
        base_column = st.selectbox('Coluna da origem para calcular custo/preço', columns, index=base_index, key=f'{key_prefix}_price_base_column')

        model_df = model if isinstance(model, pd.DataFrame) and len(model.columns) else _model_from_session()
        target_options = price_target_columns(model_df)
        selected_target = ''
        if target_options:
            default_target = default_price_target_column(model_df)
            target_index = target_options.index(default_target) if default_target in target_options else 0
            selected_target = st.selectbox('Coluna do modelo que receberá o preço calculado', target_options, index=target_index, key=f'{key_prefix}_price_target_column')
            output_column = selected_target
        else:
            manual_options = manual_target_columns(model_df)
            if manual_options:
                selected_target = st.selectbox('Escolha manualmente a coluna do modelo que receberá o preço calculado', manual_options, key=f'{key_prefix}_price_target_column_manual')
                output_column = selected_target
                st.warning('Não encontrei uma coluna claramente parecida com preço no modelo. Escolha manualmente a coluna correta.')
            else:
                selected_target = ''
                output_column = st.text_input('Nome da coluna calculada', value='Preço calculado marketplace', key=f'{key_prefix}_price_output_name')
                st.error('Não encontrei uma coluna válida do modelo para receber preço. Reconfirme se o modelo final foi anexado antes da origem.')

        with st.expander('Avançado: coluna auxiliar diferente', expanded=False):
            use_custom_output = st.checkbox('Usar nome técnico diferente da coluna do modelo', value=False, key=f'{key_prefix}_price_use_custom_output_name')
            if use_custom_output:
                custom_output = st.text_input('Nome técnico usado no mapeamento', value=str(output_column or 'Preço calculado marketplace'), key=f'{key_prefix}_price_output_name_advanced')
                custom_output = custom_output.strip()
                if custom_output:
                    output_column = custom_output
            else:
                st.caption('Padrão recomendado: calcular direto com o mesmo nome da coluna de preço do modelo.')

        margin = Decimal(str(st.number_input('Margem (%)', min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key=f'{key_prefix}_margin') or 0))
        fee = Decimal(str(st.number_input('Taxas/marketplace (%)', min_value=0.0, max_value=1000.0, value=18.0, step=1.0, key=f'{key_prefix}_fee') or 0))
        fixed = Decimal(str(st.number_input('Valor fixo por item (R$)', min_value=0.0, max_value=100000.0, value=0.0, step=1.0, key=f'{key_prefix}_fixed') or 0))

        if not enabled:
            st.session_state[UNIVERSAL_PRICE_AUTOMAP_KEY] = False
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
        st.session_state[UNIVERSAL_PRICE_BASE_COLUMN_KEY] = base_column
        st.session_state[UNIVERSAL_PRICE_COLUMN_KEY] = output_column
        st.session_state[UNIVERSAL_PRICE_TARGET_COLUMN_KEY] = selected_target or output_column
        st.session_state[UNIVERSAL_PRICE_AUTOMAP_KEY] = True
        if selected_target:
            st.success(f'Cálculo aplicado: {base_column} → {selected_target}. O mapeamento será preenchido automaticamente nessa coluna do modelo.')
        else:
            st.success(f'Cálculo aplicado na coluna de origem: {output_column}')
        return out


__all__ = [
    'UNIVERSAL_PRICE_AUTOMAP_KEY',
    'UNIVERSAL_PRICE_BASE_COLUMN_KEY',
    'UNIVERSAL_PRICE_COLUMN_KEY',
    'UNIVERSAL_PRICE_TARGET_COLUMN_KEY',
    'apply_marketplace_calculation',
    'default_base_price_column',
    'default_price_target_column',
    'format_money',
    'manual_target_columns',
    'numeric_columns',
    'parse_decimal',
    'price_target_columns',
    'render_shared_calculator',
]
