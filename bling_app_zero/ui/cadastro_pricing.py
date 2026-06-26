from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.price_calculator_plugin import (
    PRICE_TARGET_ALIASES,
    PROMO_PRICE_TARGET_ALIASES,
    apply_price_aliases,
    apply_price_calculator_plugin,
    apply_promotional_price_aliases,
    best_cost_column,
)
from bling_app_zero.ui.home_pricing_config import get_home_pricing_config
from bling_app_zero.ui.home_shared import df_signature

PRICED_SOURCE_KEY = 'df_origem_cadastro_precificada'
PRICING_ACTIVE_KEY = 'cadastro_preco_calculado_ativo'
PRICING_SOURCE_KEY = 'shared_price_calculator_source'

# Esta chave também é usada por um widget da calculadora rápida.
# Depois que o widget é instanciado, o Streamlit não permite alterar essa key manualmente.
# Por isso este módulo apenas LÊ essa chave e grava a escolha consolidada na chave legacy/cache.
PRICING_SELECTED_COST_COLUMN_KEY = 'price_calculator_source_cost_column'
PRICING_SELECTED_COST_COLUMN_LEGACY_KEY = 'global_price_source_cost_column'
CADASTRO_ORIGEM_PRICED_STATE_KEY = 'cadastro_wizard_df_para_mapear'


def apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    out = apply_price_aliases(df, calculated_column, PRICE_TARGET_ALIASES)
    return apply_promotional_price_aliases(out, 'Preço promocional', PROMO_PRICE_TARGET_ALIASES)


def _pricing_config() -> dict:
    return get_home_pricing_config()


def _pricing_enabled() -> bool:
    return bool(_pricing_config().get('enabled', False))


def _columns_as_text(df_origem: pd.DataFrame) -> list[str]:
    return list(map(str, df_origem.columns))


def _selected_cost_column(df_origem: pd.DataFrame) -> str:
    columns = _columns_as_text(df_origem)

    selected = str(st.session_state.get(PRICING_SELECTED_COST_COLUMN_KEY) or '').strip()
    if selected and selected in columns:
        return selected

    legacy_selected = str(st.session_state.get(PRICING_SELECTED_COST_COLUMN_LEGACY_KEY) or '').strip()
    if legacy_selected and legacy_selected in columns:
        return legacy_selected

    return best_cost_column(columns)


def _store_pricing_state(signature: str, selected_cost_column: str) -> None:
    st.session_state[PRICING_ACTIVE_KEY] = True
    st.session_state[f'cadastro_coluna_custo_{signature}'] = selected_cost_column
    st.session_state[PRICING_SELECTED_COST_COLUMN_LEGACY_KEY] = selected_cost_column
    st.session_state[PRICING_SOURCE_KEY] = 'price_step_plugin'


def clear_cadastro_pricing_state() -> None:
    st.session_state[PRICING_ACTIVE_KEY] = False
    st.session_state.pop(PRICED_SOURCE_KEY, None)
    st.session_state.pop(CADASTRO_ORIGEM_PRICED_STATE_KEY, None)


def _promo_discount(config: dict) -> float:
    try:
        return max(0.0, float(config.get('promo_discount_percent') or 0.0))
    except Exception:
        return 0.0


def _apply_simple_reprice_promotional_result(df: pd.DataFrame, selected_cost_column: str, config: dict) -> pd.DataFrame:
    """Reajuste simples: Preco recebe o valor reajustado e Preco Promocional recebe o desconto."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if str(config.get('quick_reprice_mode') or '').strip().lower() != 'markup':
        return df
    promo_percent = _promo_discount(config)
    if promo_percent <= 0:
        return df
    if not selected_cost_column or selected_cost_column not in df.columns:
        return df

    from bling_app_zero.core.easy_reprice import calc_easy_promo_price, calc_easy_sale_price, money_or_empty

    out = df.copy().fillna('')
    base_config = dict(config)
    base_config['promo_discount_percent'] = 0.0
    sale_values = out[selected_cost_column].apply(lambda value: calc_easy_sale_price(value, base_config))
    promo_values = sale_values.apply(lambda value: calc_easy_promo_price(value, promo_percent))
    out['Preço de venda'] = sale_values.apply(money_or_empty)
    out['Preço promocional'] = promo_values.apply(money_or_empty)
    out = apply_price_aliases(out, 'Preço de venda', PRICE_TARGET_ALIASES)
    out = apply_promotional_price_aliases(out, 'Preço promocional', PROMO_PRICE_TARGET_ALIASES)
    return out


def apply_cadastro_pricing(df_origem: pd.DataFrame, *, channel: str = 'etapa_preco') -> pd.DataFrame:
    """Aplica a precificação configurada na etapa Preço.

    BLINGMODULAR 2:
    - a calculadora visual pertence à etapa Preço;
    - o mapeamento não deve abrir nem recalcular a calculadora;
    - esta função apenas transforma a origem em origem precificada e salva o
      resultado em session_state para as próximas etapas consumirem.
    """
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return df_origem

    config = _pricing_config()
    selected_cost_column = _selected_cost_column(df_origem)
    result = apply_price_calculator_plugin(
        df_origem,
        enabled=_pricing_enabled(),
        config=config,
        cost_column=selected_cost_column,
        output_column='Preço de venda',
        channel=channel,
        aliases=PRICE_TARGET_ALIASES,
        promo_output_column='Preço promocional',
        promo_aliases=PROMO_PRICE_TARGET_ALIASES,
    )

    if not result.applied:
        clear_cadastro_pricing_state()
        return result.df

    origem_signature = df_signature(df_origem)
    _store_pricing_state(origem_signature, result.source_column)
    priced_df = _apply_simple_reprice_promotional_result(result.df, result.source_column, config)
    st.session_state[PRICED_SOURCE_KEY] = priced_df
    st.session_state[CADASTRO_ORIGEM_PRICED_STATE_KEY] = priced_df
    return priced_df


def render_cadastro_pricing(df_origem: pd.DataFrame, *, channel: str = 'compatibilidade') -> pd.DataFrame:
    """Compatibilidade legado.

    Mantido para imports antigos, mas o fluxo principal agora chama
    `apply_cadastro_pricing()` diretamente na etapa Preço.
    """
    return apply_cadastro_pricing(df_origem, channel=channel)


__all__ = [
    'PRICE_TARGET_ALIASES',
    'PROMO_PRICE_TARGET_ALIASES',
    'PRICED_SOURCE_KEY',
    'PRICING_ACTIVE_KEY',
    'PRICING_SELECTED_COST_COLUMN_KEY',
    'PRICING_SELECTED_COST_COLUMN_LEGACY_KEY',
    'apply_calculated_price_aliases',
    'apply_cadastro_pricing',
    'best_cost_column',
    'clear_cadastro_pricing_state',
    'render_cadastro_pricing',
]
