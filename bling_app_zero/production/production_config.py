from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

PRODUCTION_MODE_KEY = 'mapeiaai_production_mode'
ADMIN_MODE_KEY = 'mapeiaai_admin_mode_enabled'
ADMIN_PASSWORD_INPUT_KEY = 'mapeiaai_admin_password_input'


@dataclass(frozen=True)
class ProductionConfig:
    enabled: bool
    app_domain: str
    environment: str
    database_url: str
    auth_provider: str
    payment_provider: str
    webhook_secret_configured: bool


def _secret_value(name: str, default: str = '') -> str:
    env_value = os.getenv(name)
    if env_value:
        return str(env_value).strip()
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return default


def _nested_secret_value(section: str, name: str, default: str = '') -> str:
    try:
        section_data = st.secrets.get(section, {})
        if hasattr(section_data, 'get'):
            value = section_data.get(name, default)
            return str(value or default).strip()
    except Exception:
        pass
    return default


def admin_key() -> str:
    return _secret_value('MAPEIAAI_ADMIN_KEY') or _nested_secret_value('security', 'admin_key')


def admin_mode_enabled() -> bool:
    env_flag = str(os.getenv('MAPEIAAI_ADMIN_MODE') or '').strip().lower()
    if env_flag in {'1', 'true', 'yes', 'admin', 'debug'}:
        return True
    if bool(st.session_state.get(ADMIN_MODE_KEY, False)):
        return True
    return False


def set_admin_mode(enabled: bool) -> None:
    st.session_state[ADMIN_MODE_KEY] = bool(enabled)


def production_mode_enabled() -> bool:
    env_flag = str(os.getenv('MAPEIAAI_PRODUCTION_MODE') or '').strip().lower()
    if env_flag in {'1', 'true', 'yes', 'prod', 'production'}:
        return True
    return bool(st.session_state.get(PRODUCTION_MODE_KEY, False))


def _normalized_environment() -> str:
    raw = _secret_value('MAPEIAAI_ENVIRONMENT', '').strip().lower()
    if raw:
        return raw
    return 'production' if production_mode_enabled() else 'development'


def get_production_config() -> ProductionConfig:
    return ProductionConfig(
        enabled=production_mode_enabled(),
        app_domain=_secret_value('MAPEIAAI_APP_DOMAIN', 'app.mapeiaAI.com'),
        environment=_normalized_environment(),
        database_url=_secret_value('DATABASE_URL', ''),
        auth_provider=_secret_value('MAPEIAAI_AUTH_PROVIDER', 'supabase'),
        payment_provider=_secret_value('MAPEIAAI_PAYMENT_PROVIDER', 'mercadopago'),
        webhook_secret_configured=bool(_secret_value('MAPEIAAI_PAYMENT_WEBHOOK_SECRET', '')),
    )


__all__ = [
    'ADMIN_MODE_KEY',
    'ADMIN_PASSWORD_INPUT_KEY',
    'PRODUCTION_MODE_KEY',
    'ProductionConfig',
    'admin_key',
    'admin_mode_enabled',
    'get_production_config',
    'production_mode_enabled',
    'set_admin_mode',
]
