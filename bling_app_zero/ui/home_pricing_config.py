from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.shared_price_calculator import normalize_shared_price_config
from bling_app_zero.v2.price_multistore.quick_ui import (
    GLOBAL_PRICE_READY_KEY,
    GLOBAL_PRICE_RESULT_KEY,
    render_quick_price_calculator,
)

HOME_PRICING_CONFIG_KEY = 'home_pricing_config'

CALCULATOR_MODES = ['Lucro nominal', 'Margem de contribuição', 'Preço fixo']
CALCULATOR_MODE_MAP = {
    'Lucro nominal': 'nominal_profit',
    'Margem de contribuição': 'contribution_margin',
    'Preço fixo': 'fixed_sale_price',
}
CALCULATOR_MODE_LABELS = {value: key for key, value in CALCULATOR_MODE_MAP.items()}


@dataclass(frozen=True)
class HomePricingDefaults:
    enabled: bool = False
    calculator_mode: str = 'nominal_profit'
    marketplace_fee_percent: float = 0.0
    tax_percent: float = 0.0
    freight_cost: float = 0.0
    other_sale_fees_percent: float = 0.0
    desired_nominal_profit: float = 0.0
    desired_contribution_margin_percent: float = 0.0
    desired_sale_price: float = 0.0
    supplier_term_days: float = 15.0
    stock_turnover_days: float = 30.0
    promo_discount_percent: float = 0.0


def default_home_pricing_config() -> dict[str, Any]:
    defaults = HomePricingDefaults()
    return normalize_shared_price_config(
        {
            'enabled': defaults.enabled,
            'calculator_mode': defaults.calculator_mode,
            'marketplace_fee_percent': defaults.marketplace_fee_percent,
            'tax_percent': defaults.tax_percent,
            'freight_cost': defaults.freight_cost,
            'other_sale_fees_percent': defaults.other_sale_fees_percent,
            'desired_nominal_profit': defaults.desired_nominal_profit,
            'desired_contribution_margin_percent': defaults.desired_contribution_margin_percent,
            'desired_sale_price': defaults.desired_sale_price,
            'supplier_term_days': defaults.supplier_term_days,
            'stock_turnover_days': defaults.stock_turnover_days,
            'promo_discount_percent': defaults.promo_discount_percent,
        }
    )


def normalize_home_pricing_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = default_home_pricing_config()
    if isinstance(raw, dict):
        config.update(raw)
    normalized = normalize_shared_price_config(config)
    normalized['enabled'] = bool(config.get('enabled', False))
    return normalized


def get_home_pricing_config() -> dict[str, Any]:
    config = normalize_home_pricing_config(st.session_state.get(HOME_PRICING_CONFIG_KEY))
    st.session_state[HOME_PRICING_CONFIG_KEY] = config
    return config


def set_home_pricing_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_home_pricing_config(config)
    st.session_state[HOME_PRICING_CONFIG_KEY] = normalized
    st.session_state['home_precificacao_inicial'] = bool(normalized.get('enabled', False))
    st.session_state['cadastro_preco_calculado_ativo'] = bool(normalized.get('enabled', False))
    st.session_state['shared_price_calculator_enabled'] = bool(normalized.get('enabled', False))
    return normalized


def disable_home_pricing() -> dict[str, Any]:
    config = get_home_pricing_config()
    config['enabled'] = False
    return set_home_pricing_config(config)


def _mode_label(config: dict[str, Any]) -> str:
    mode = str(config.get('calculator_mode') or 'nominal_profit')
    return CALCULATOR_MODE_LABELS.get(mode, 'Lucro nominal')


def _config_from_global_result(*, source_df: pd.DataFrame | None = None) -> dict[str, Any]:
    result = st.session_state.get(GLOBAL_PRICE_RESULT_KEY)
    if result is None:
        current = get_home_pricing_config()
        current['enabled'] = bool(st.session_state.get(GLOBAL_PRICE_READY_KEY, False))
        return current

    sale_price = float(getattr(result, 'sale_price', 0.0) or 0.0)
    cost = float(getattr(result, 'cost', 0.0) or 0.0)
    profit = float(getattr(result, 'profit', 0.0) or 0.0)
    margin = float(getattr(result, 'margin', 0.0) or 0.0)
    fee_percent = float(getattr(result, 'marketplace_fee_percent', 0.0) or 0.0)
    fixed_fee = float(getattr(result, 'fixed_fee', 0.0) or 0.0)
    freight = float(getattr(result, 'freight', 0.0) or 0.0)
    tax_value = float(getattr(result, 'tax', 0.0) or 0.0)
    tax_percent = (tax_value / sale_price * 100.0) if sale_price else 0.0
    extra_cost = float(getattr(result, 'extra_cost', 0.0) or 0.0)
    has_source = isinstance(source_df, pd.DataFrame) and not source_df.empty

    if has_source:
        calculator_mode = 'nominal_profit'
        desired_sale_price = 0.0
        desired_nominal_profit = max(profit, 0.0)
        desired_contribution_margin_percent = max(margin, 0.0)
    else:
        calculator_mode = 'fixed_sale_price'
        desired_sale_price = sale_price
        desired_nominal_profit = 0.0
        desired_contribution_margin_percent = 0.0

    return normalize_home_pricing_config(
        {
            'enabled': True,
            'calculator_mode': calculator_mode,
            'marketplace_fee_percent': fee_percent,
            'tax_percent': tax_percent,
            'freight_cost': freight + fixed_fee + extra_cost,
            'other_sale_fees_percent': 0.0,
            'desired_nominal_profit': desired_nominal_profit,
            'desired_contribution_margin_percent': desired_contribution_margin_percent,
            'desired_sale_price': desired_sale_price,
            'supplier_term_days': 0.0,
            'stock_turnover_days': 0.0,
            'promo_discount_percent': 0.0,
            'source_sample_cost': cost,
        }
    )


def render_home_pricing_config_form(source_df: pd.DataFrame | None = None) -> dict[str, Any]:
    st.markdown('##### Calculadora única de preço')
    st.caption('Com planilha, a calculadora localiza a coluna de custo e calcula linha por linha. Sem planilha, funciona como simulação avulsa na tela.')
    render_quick_price_calculator(embedded=True, source_df=source_df)
    config = _config_from_global_result(source_df=source_df)
    if bool(config.get('enabled', False)):
        if isinstance(source_df, pd.DataFrame) and not source_df.empty:
            st.success(f'Calculadora pronta para aplicar preço linha a linha. Modo: {_mode_label(config)}.')
        else:
            st.success('Simulação avulsa concluída. O preço calculado aparece apenas na tela enquanto não houver fonte de dados.')
    else:
        st.warning('Calcule um preço para liberar a referência de precificação.')
    return config


__all__ = [
    'HOME_PRICING_CONFIG_KEY',
    'default_home_pricing_config',
    'disable_home_pricing',
    'get_home_pricing_config',
    'normalize_home_pricing_config',
    'render_home_pricing_config_form',
    'set_home_pricing_config',
]
