from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

HOME_PRICING_CONFIG_KEY = 'home_pricing_config'


@dataclass(frozen=True)
class HomePricingDefaults:
    enabled: bool = False
    profit_percent: float = 50.0
    tax_percent: float = 0.0
    fee_percent: float = 0.0
    commission_percent: float = 0.0
    fixed_value: float = 0.0


def default_home_pricing_config() -> dict[str, Any]:
    defaults = HomePricingDefaults()
    return {
        'enabled': defaults.enabled,
        'profit_percent': defaults.profit_percent,
        'tax_percent': defaults.tax_percent,
        'fee_percent': defaults.fee_percent,
        'discount_percent': defaults.commission_percent,
        'fixed_value': defaults.fixed_value,
    }


def normalize_home_pricing_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = default_home_pricing_config()
    if isinstance(raw, dict):
        config.update({key: raw.get(key, value) for key, value in config.items()})

    config['enabled'] = bool(config.get('enabled', False))
    for key in ['profit_percent', 'tax_percent', 'fee_percent', 'discount_percent', 'fixed_value']:
        try:
            config[key] = float(config.get(key, 0.0) or 0.0)
        except Exception:
            config[key] = 0.0
        if config[key] < 0:
            config[key] = 0.0
    return config


def get_home_pricing_config() -> dict[str, Any]:
    config = normalize_home_pricing_config(st.session_state.get(HOME_PRICING_CONFIG_KEY))
    st.session_state[HOME_PRICING_CONFIG_KEY] = config
    return config


def set_home_pricing_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_home_pricing_config(config)
    st.session_state[HOME_PRICING_CONFIG_KEY] = normalized
    st.session_state['home_precificacao_inicial'] = bool(normalized.get('enabled', False))
    st.session_state['cadastro_preco_calculado_ativo'] = bool(normalized.get('enabled', False))
    return normalized


def disable_home_pricing() -> dict[str, Any]:
    config = get_home_pricing_config()
    config['enabled'] = False
    return set_home_pricing_config(config)


def render_home_pricing_config_form() -> dict[str, Any]:
    current = get_home_pricing_config()
    st.markdown('##### Calculadora de preço de venda')
    st.caption('Informe lucro, impostos, taxas e valor fixo. O sistema usa esses dados para sugerir o preço de venda no cadastro.')

    col_a, col_b, col_c = st.columns(3)
    profit_percent = col_a.number_input(
        'Lucro desejado %',
        min_value=0.0,
        value=float(current.get('profit_percent', 50.0)),
        step=1.0,
        key='home_pricing_profit_percent',
    )
    tax_percent = col_b.number_input(
        'Impostos %',
        min_value=0.0,
        value=float(current.get('tax_percent', 0.0)),
        step=1.0,
        key='home_pricing_tax_percent',
    )
    fee_percent = col_c.number_input(
        'Taxas da venda %',
        min_value=0.0,
        value=float(current.get('fee_percent', 0.0)),
        step=1.0,
        key='home_pricing_fee_percent',
    )

    col_d, col_e = st.columns(2)
    commission_percent = col_d.number_input(
        'Comissão / marketplace %',
        min_value=0.0,
        value=float(current.get('discount_percent', 0.0)),
        step=1.0,
        key='home_pricing_discount_percent',
    )
    fixed_value = col_e.number_input(
        'Custo fixo R$',
        min_value=0.0,
        value=float(current.get('fixed_value', 0.0)),
        step=1.0,
        key='home_pricing_fixed_value',
    )

    st.caption('A calculadora parte do custo do produto. No cadastro, o sistema tenta escolher automaticamente a melhor coluna de custo.')

    preview = {
        'enabled': True,
        'profit_percent': float(profit_percent),
        'tax_percent': float(tax_percent),
        'fee_percent': float(fee_percent),
        'discount_percent': float(commission_percent),
        'fixed_value': float(fixed_value),
    }
    return preview
