from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.shared_price_calculator import normalize_shared_price_config
from bling_app_zero.ui.easy_price_ui import render_easy_price_calculator
from bling_app_zero.v2.price_multistore.quick_ui import (
    GLOBAL_PRICE_CONFIG_KEY,
    GLOBAL_PRICE_READY_KEY,
    GLOBAL_PRICE_RESULT_KEY,
    PRICE_CALCULATOR_CONFIG_KEY,
    PRICE_CALCULATOR_PROMO_DISCOUNT_KEY,
    PRICE_CALCULATOR_READY_KEY,
    PRICE_CALCULATOR_RESULT_KEY,
)

HOME_PRICING_CONFIG_KEY = 'home_pricing_config'
PRICE_PROMO_EXTRA_KEYS = ('promo_action', 'promo_base')


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
    return normalize_shared_price_config(defaults.__dict__)


def normalize_home_pricing_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = default_home_pricing_config()
    if isinstance(raw, dict):
        config.update(raw)
    normalized = normalize_shared_price_config(config)
    normalized['enabled'] = bool(config.get('enabled', False))
    for key in PRICE_PROMO_EXTRA_KEYS:
        if key in config:
            normalized[key] = str(config.get(key) or '').strip()
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


def _calculator_config() -> dict[str, Any]:
    config = st.session_state.get(PRICE_CALCULATOR_CONFIG_KEY)
    if isinstance(config, dict):
        return config
    config = st.session_state.get(GLOBAL_PRICE_CONFIG_KEY)
    if isinstance(config, dict):
        return config
    return {}


def _calculator_ready() -> bool:
    return bool(st.session_state.get(PRICE_CALCULATOR_READY_KEY, st.session_state.get(GLOBAL_PRICE_READY_KEY, False)))


def _promo_discount_from_state() -> float:
    try:
        return max(0.0, float(st.session_state.get(PRICE_CALCULATOR_PROMO_DISCOUNT_KEY, 0.0) or 0.0))
    except Exception:
        return 0.0


def _config_from_global_result(*, source_df: pd.DataFrame | None = None) -> dict[str, Any]:
    raw = _calculator_config()
    if raw:
        raw = dict(raw)
        raw['enabled'] = True
        raw['promo_discount_percent'] = max(float(raw.get('promo_discount_percent') or 0.0), _promo_discount_from_state())
        return normalize_home_pricing_config(raw)
    current = get_home_pricing_config()
    current['enabled'] = _calculator_ready()
    current['promo_discount_percent'] = _promo_discount_from_state()
    return current


def _mode_label(config: dict[str, Any]) -> str:
    mode = str(config.get('quick_reprice_mode') or '')
    if mode == 'net_margin':
        return 'Preço mínimo real'
    if mode == 'markup':
        return 'Reajuste simples'
    return 'Calculadora'


def render_home_pricing_config_form(source_df: pd.DataFrame | None = None) -> dict[str, Any]:
    render_easy_price_calculator(source_df=source_df)
    config = _config_from_global_result(source_df=source_df)
    if bool(config.get('enabled', False)):
        promo = float(config.get('promo_discount_percent', 0.0) or 0.0)
        text = f'Preço pronto. Modo: {_mode_label(config)}.'
        if promo > 0:
            text += f' Promocional: -{promo:.2f}%.'
        st.success(text)
    else:
        st.warning('Aplique a calculadora para liberar a precificação.')
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
