from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

PRODUCTION_MODE_KEY = 'mapeiaai_production_mode'


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


def production_mode_enabled() -> bool:
    env_flag = str(os.getenv('MAPEIAAI_PRODUCTION_MODE') or '').strip().lower()
    if env_flag in {'1', 'true', 'yes', 'prod', 'production'}:
        return True
    return bool(st.session_state.get(PRODUCTION_MODE_KEY, False))


def get_production_config() -> ProductionConfig:
    return ProductionConfig(
        enabled=production_mode_enabled(),
        app_domain=_secret_value('MAPEIAAI_APP_DOMAIN', 'app.mapeiaAI.com'),
        environment=_secret_value('MAPEIAAI_ENVIRONMENT', 'development'),
        database_url=_secret_value('DATABASE_URL', ''),
        auth_provider=_secret_value('MAPEIAAI_AUTH_PROVIDER', 'supabase'),
        payment_provider=_secret_value('MAPEIAAI_PAYMENT_PROVIDER', 'mercadopago'),
        webhook_secret_configured=bool(_secret_value('MAPEIAAI_PAYMENT_WEBHOOK_SECRET', '')),
    )


__all__ = ['PRODUCTION_MODE_KEY', 'ProductionConfig', 'get_production_config', 'production_mode_enabled']
