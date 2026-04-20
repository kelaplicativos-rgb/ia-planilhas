
# 🔥 BLINGFIX: REMOVIDO bling_token_store externo
# Agora usa armazenamento interno via JSON + session_state

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote
from pathlib import Path

import httpx
import streamlit as st


# ============================================================
# 🔥 TOKEN STORE INTERNO (SUBSTITUI BlingTokenStore)
# ============================================================

class BlingTokenStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        try:
            if self.path.exists():
                return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self, data: dict):
        try:
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save(self, user_key: str, payload: dict):
        data = self._load()
        data[user_key] = payload
        self._save(data)

    def get(self, user_key: str) -> dict:
        return self._load().get(user_key, {})

    def delete(self, user_key: str):
        data = self._load()
        data.pop(user_key, None)
        self._save(data)

    def is_expired(self, token: dict) -> bool:
        created = int(token.get("created_at", 0))
        expires = int(token.get("expires_in", 0))
        return time.time() > (created + expires - 60)

    def update_company_name(self, name: str, user_key: str):
        data = self._load()
        if user_key in data:
            data[user_key]["company_name"] = name
            self._save(data)


# ============================================================
# RESTO DO ARQUIVO ORIGINAL (mantido)
# ============================================================

def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, list):
            return str(value[0] if value else "").strip()
        return str(value).strip()
    except Exception:
        return ""


def _safe_json_dict(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return _safe_str(value[0] if value else "")
        return _safe_str(value)
    except Exception:
        return ""


@dataclass
class BlingSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    revoke_url: str
    api_base_url: str
    token_store_path: str


class BlingAuthManager:
    def __init__(self, user_key: str = "default") -> None:
        cfg = st.secrets.get("bling", {})

        self.user_key = _safe_str(user_key or "default") or "default"

        self.settings = BlingSettings(
            client_id=_safe_str(cfg.get("client_id")),
            client_secret=_safe_str(cfg.get("client_secret")),
            redirect_uri=_safe_str(cfg.get("redirect_uri")),
            authorize_url="https://www.bling.com.br/Api/v3/oauth/authorize",
            token_url="https://www.bling.com.br/Api/v3/oauth/token",
            revoke_url="https://www.bling.com.br/Api/v3/oauth/revoke",
            api_base_url="https://api.bling.com.br/Api/v3",
            token_store_path="bling_app_zero/output/bling_tokens.json",
        )

        self.store = BlingTokenStore(self.settings.token_store_path)
        self.client = httpx.Client(timeout=30.0)

    def is_configured(self) -> bool:
        return bool(
            self.settings.client_id
            and self.settings.client_secret
            and self.settings.redirect_uri
        )

    def _basic_auth(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode()
        return f"Basic {base64.b64encode(raw).decode()}"

    def _headers_form(self) -> Dict[str, str]:
        return {
            "Authorization": self._basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def generate_auth_url(self) -> str:
        state = secrets.token_urlsafe(24)
        st.session_state["_oauth_state"] = state

        return (
            f"{self.settings.authorize_url}"
            f"?response_type=code"
            f"&client_id={self.settings.client_id}"
            f"&redirect_uri={quote(self.settings.redirect_uri)}"
            f"&state={state}"
        )

    def exchange_code_for_token(self, code: str):
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }

        r = self.client.post(self.settings.token_url, headers=self._headers_form(), data=data)
        payload = _safe_json_dict(r.text)

        if "access_token" not in payload:
            return False, payload

        payload["created_at"] = int(time.time())
        self.store.save(self.user_key, payload)
        return True, payload

    def get_connection_status(self):
        token = self.store.get(self.user_key)
        conectado = bool(token) and not self.store.is_expired(token)

        return {
            "connected": conectado,
            "company_name": token.get("company_name"),
        }


# ============================================================
# UI
# ============================================================

def render_conectar_bling():
    auth = BlingAuthManager()

    if not auth.is_configured():
        st.error("Configure secrets do Bling")
        return

    status = auth.get_connection_status()

    if status["connected"]:
        st.success("Conectado ao Bling")
        return

    url = auth.generate_auth_url()

    st.markdown(
        f"""
        <a href="{url}">
            <button style="width:100%;padding:10px;background:#16a34a;color:white;border:none;border-radius:8px;">
                Conectar com Bling
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )
