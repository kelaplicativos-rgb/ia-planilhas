from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class EnterpriseConfig:
    enabled: bool
    supabase_url: str
    supabase_anon_key: str
    require_login: bool


def _secret(path: str, default: str = "") -> str:
    try:
        node = st.secrets
        for part in path.split("."):
            node = node[part]
        return str(node)
    except Exception:
        return default


def get_enterprise_config() -> EnterpriseConfig:
    supabase_url = _secret("supabase.url", os.getenv("SUPABASE_URL", ""))
    supabase_anon_key = _secret("supabase.anon_key", os.getenv("SUPABASE_ANON_KEY", ""))
    require_login_raw = _secret("enterprise.require_login", os.getenv("ENTERPRISE_REQUIRE_LOGIN", "false"))
    enabled_raw = _secret("enterprise.enabled", os.getenv("ENTERPRISE_ENABLED", "false"))

    return EnterpriseConfig(
        enabled=str(enabled_raw).lower() in {"1", "true", "yes", "sim"},
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        require_login=str(require_login_raw).lower() in {"1", "true", "yes", "sim"},
    )
