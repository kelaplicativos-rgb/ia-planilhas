from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from bling_app_zero.core.shared_price_calculator import normalize_shared_price_config

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
    desired_nominal_profit: float = 15.0
    desired_contribution_margin_percent: float = 50.0
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


def render_home_pricing_config_form() -> dict[str, Any]:
    current = get_home_pricing_config()
    st.markdown('##### Calculadora compartilhada de preço')
    st.caption('Mesma lógica da atualização de preços multiloja. Use para origem por site ou anexo antes do mapeamento.')

    calculator_mode_label = st.radio(
        'Como deseja calcular?',
        CALCULATOR_MODES,
        index=CALCULATOR_MODES.index(_mode_label(current)),
        horizontal=True,
        key='home_pricing_calculator_mode',
    )
    calculator_mode = CALCULATOR_MODE_MAP[calculator_mode_label]

    c1, c2, c3, c4 = st.columns(4)
    marketplace_fee = c1.number_input('Taxa marketplace %', min_value=0.0, value=float(current.get('marketplace_fee_percent', 0.0)), step=0.5, key='home_pricing_marketplace_fee')
    tax = c2.number_input('Imposto %', min_value=0.0, value=float(current.get('tax_percent', 0.0)), step=0.5, key='home_pricing_tax_percent')
    freight = c3.number_input('Frete R$', min_value=0.0, value=float(current.get('freight_cost', 0.0)), step=0.5, key='home_pricing_freight_cost')
    other_fees = c4.number_input('Outras taxas %', min_value=0.0, value=float(current.get('other_sale_fees_percent', 0.0)), step=0.5, key='home_pricing_other_fees')

    c5, c6, c7, c8 = st.columns(4)
    if calculator_mode == 'nominal_profit':
        desired_nominal_profit = c5.number_input('Quero ganhar R$', min_value=0.0, value=float(current.get('desired_nominal_profit', 15.0)), step=0.5, key='home_pricing_desired_nominal_profit')
        desired_margin = float(current.get('desired_contribution_margin_percent', 0.0) or 0.0)
        desired_sale_price = float(current.get('desired_sale_price', 0.0) or 0.0)
    elif calculator_mode == 'contribution_margin':
        desired_margin = c5.number_input('Quero margem de %', min_value=0.0, value=float(current.get('desired_contribution_margin_percent', 50.0)), step=0.5, key='home_pricing_desired_margin')
        desired_nominal_profit = float(current.get('desired_nominal_profit', 0.0) or 0.0)
        desired_sale_price = float(current.get('desired_sale_price', 0.0) or 0.0)
    else:
        desired_sale_price = c5.number_input('Quero vender por R$', min_value=0.0, value=float(current.get('desired_sale_price', 0.0)), step=0.5, key='home_pricing_desired_sale_price')
        desired_nominal_profit = float(current.get('desired_nominal_profit', 0.0) or 0.0)
        desired_margin = float(current.get('desired_contribution_margin_percent', 0.0) or 0.0)

    supplier_term = c6.number_input('Prazo fornecedor (dias)', min_value=0.0, value=float(current.get('supplier_term_days', 15.0)), step=1.0, key='home_pricing_supplier_term')
    stock_turnover = c7.number_input('Giro estoque (dias)', min_value=0.0, value=float(current.get('stock_turnover_days', 30.0)), step=1.0, key='home_pricing_stock_turnover')
    promo = c8.number_input('Promo %', min_value=0.0, value=float(current.get('promo_discount_percent', 0.0)), step=0.5, key='home_pricing_promo')

    st.caption('A calculadora parte da coluna de custo detectada automaticamente na origem do fornecedor.')

    return normalize_home_pricing_config(
        {
            'enabled': True,
            'calculator_mode': calculator_mode,
            'marketplace_fee_percent': float(marketplace_fee),
            'tax_percent': float(tax),
            'freight_cost': float(freight),
            'other_sale_fees_percent': float(other_fees),
            'desired_nominal_profit': float(desired_nominal_profit),
            'desired_contribution_margin_percent': float(desired_margin),
            'desired_sale_price': float(desired_sale_price),
            'supplier_term_days': float(supplier_term),
            'stock_turnover_days': float(stock_turnover),
            'promo_discount_percent': float(promo),
        }
    )


__all__ = [
    'HOME_PRICING_CONFIG_KEY',
    'default_home_pricing_config',
    'disable_home_pricing',
    'get_home_pricing_config',
    'normalize_home_pricing_config',
    'render_home_pricing_config_form',
    'set_home_pricing_config',
]
