from __future__ import annotations

from typing import Any

import httpx

from bling_app_zero.enterprise.config import get_enterprise_config


def cloud_enabled() -> bool:
    cfg = get_enterprise_config()
    return bool(cfg.enabled and cfg.supabase_url and cfg.supabase_anon_key)


def _headers() -> dict[str, str]:
    cfg = get_enterprise_config()
    return {
        "apikey": cfg.supabase_anon_key,
        "Authorization": f"Bearer {cfg.supabase_anon_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def insert_row(table: str, payload: dict[str, Any]) -> tuple[bool, Any]:
    cfg = get_enterprise_config()
    if not cloud_enabled():
        return False, "cloud disabled"

    url = f"{cfg.supabase_url.rstrip('/')}/rest/v1/{table}"
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(url, headers=_headers(), json=payload)
        if response.status_code >= 400:
            return False, response.text
        return True, response.json()
    except Exception as exc:
        return False, str(exc)


def select_rows(table: str, query: str = "", limit: int = 50) -> tuple[bool, Any]:
    cfg = get_enterprise_config()
    if not cloud_enabled():
        return False, "cloud disabled"

    suffix = f"?limit={limit}"
    if query:
        suffix = f"?{query}&limit={limit}"

    url = f"{cfg.supabase_url.rstrip('/')}/rest/v1/{table}{suffix}"
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=_headers())
        if response.status_code >= 400:
            return False, response.text
        return True, response.json()
    except Exception as exc:
        return False, str(exc)
