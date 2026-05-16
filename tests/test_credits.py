from __future__ import annotations

import importlib
from pathlib import Path


def test_credits_core_is_disabled_by_default(monkeypatch) -> None:
    st = importlib.import_module('streamlit')
    credits = importlib.import_module('bling_app_zero.core.credits')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    check = credits.check_mapping_credit('abc')

    assert check.enabled is False
    assert check.allowed is True
    assert credits.consume_mapping_credit('abc', operation='cadastro') is True


def test_credits_block_when_enabled_without_balance(monkeypatch) -> None:
    st = importlib.import_module('streamlit')
    credits = importlib.import_module('bling_app_zero.core.credits')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    st.session_state[credits.CREDITS_ENABLED_KEY] = True
    credits.set_credit_balance(0)
    check = credits.check_mapping_credit('abc')

    assert check.enabled is True
    assert check.allowed is False
    assert credits.consume_mapping_credit('abc', operation='cadastro') is False


def test_credits_consume_once_per_signature(monkeypatch) -> None:
    st = importlib.import_module('streamlit')
    credits = importlib.import_module('bling_app_zero.core.credits')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    st.session_state[credits.CREDITS_ENABLED_KEY] = True
    credits.set_credit_balance(2)

    assert credits.consume_mapping_credit('abc', operation='cadastro') is True
    assert credits.get_credit_balance() == 1
    assert credits.consume_mapping_credit('abc', operation='cadastro') is True
    assert credits.get_credit_balance() == 1


def test_credit_sidebar_and_mapping_confirmation_are_plugged() -> None:
    sidebar = Path('bling_app_zero/ui/sidebar_tools.py').read_text(encoding='utf-8')
    confirmation = Path('bling_app_zero/ui/mapping_confirmation.py').read_text(encoding='utf-8')
    config = Path('bling_app_zero/core/app_config.py').read_text(encoding='utf-8')

    assert 'Créditos MapeiaAI' in sidebar
    assert 'render_credits_sidebar' in sidebar
    assert 'consume_mapping_credit' in confirmation
    assert 'check_mapping_credit' in confirmation
    assert 'MapeiaAI' in config
    assert 'Mapeia.AI' not in config


def test_business_config_centralizes_domain_and_packages() -> None:
    business = importlib.import_module('bling_app_zero.core.business_config')
    sidebar = Path('bling_app_zero/ui/credits_sidebar.py').read_text(encoding='utf-8')
    hero = Path('bling_app_zero/ui/layout/components.py').read_text(encoding='utf-8')
    ai_sidebar = Path('bling_app_zero/ui/ai_sidebar.py').read_text(encoding='utf-8')

    assert business.BRAND_NAME == 'MapeiaAI'
    assert business.APP_PUBLIC_DOMAIN == 'app.mapeiaAI.com'
    assert business.CREDIT_PRICE_BRL == 1.0
    assert business.CREDIT_PACKAGES
    assert 'APP_PUBLIC_DOMAIN' in sidebar
    assert 'CREDIT_PACKAGES' in sidebar
    assert 'MapeiaAI' in hero
    assert 'Mapeia.AI' not in hero
    assert 'IA do MapeiaAI' in ai_sidebar
    assert 'IA do Mapeia.AI' not in ai_sidebar
