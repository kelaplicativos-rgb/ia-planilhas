from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple
from urllib.parse import quote

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore


# =========================
# HELPERS
# =========================
def _safe_str(value: object) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, list):
            return str(value[0] if value else "").strip()
        return str(value).strip()
    except Exception:
        return ""


def _safe_json(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# =========================
# SETTINGS
# =========================
@dataclass
class BlingSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    token_store_path: str


# =========================
# AUTH MANAGER
# =========================
class BlingAuthManager:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = _safe_str(user_key or "default")

        cfg = st.secrets.get("bling", {})

        self.settings = BlingSettings(
            client_id=_safe_str(cfg.get("client_id")),
            client_secret=_safe_str(cfg.get("client_secret")),
            redirect_uri=_safe_str(cfg.get("redirect_uri")),
            authorize_url="https://www.bling.com.br/Api/v3/oauth/authorize",
            token_url="https://www.bling.com.br/Api/v3/oauth/token",
            token_store_path=_safe_str(cfg.get("token_store_path"))
            or "bling_app_zero/output/bling_tokens.json",
        )

        self.store = BlingTokenStore(self.settings.token_store_path)

        self.client = httpx.Client(timeout=30.0)

    # =========================
    # CONFIG
    # =========================
    def is_configured(self) -> bool:
        return bool(
            self.settings.client_id
            and self.settings.client_secret
            and self.settings.redirect_uri
        )

    # =========================
    # 🔥 URL OAUTH (BLINDADO)
    # =========================
    def generate_auth_url(self) -> str:
        """
        Geração manual (SEM urlencode) para garantir redirect_uri SEMPRE presente
        """

        if not self.is_configured():
            st.session_state["_bling_debug_auth_error"] = "OAuth não configurado"
            return ""

        redirect_uri = self.settings.redirect_uri.strip()

        if not redirect_uri:
            st.session_state["_bling_debug_auth_error"] = "redirect_uri vazio"
            return ""

        state = secrets.token_urlsafe(24)
        st.session_state["_oauth_state"] = state

        redirect_encoded = quote(redirect_uri, safe="")

        auth_url = (
            f"https://www.bling.com.br/Api/v3/oauth/authorize"
            f"?response_type=code"
            f"&client_id={self.settings.client_id}"
            f"&redirect_uri={redirect_encoded}"
            f"&state={state}"
        )

        # DEBUG FORÇADO
        st.session_state["_bling_debug_auth_url"] = auth_url
        st.session_state["_bling_debug_redirect_uri"] = redirect_uri

        return auth_url

    # =========================
    # TOKEN
    # =========================
    def _basic_auth(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode()
        return f"Basic {base64.b64encode(raw).decode()}"

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        if not code:
            return False, "Código ausente"

        headers = {
            "Authorization": self._basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }

        try:
            resp = self.client.post(self.settings.token_url, headers=headers, data=data)

            payload = _safe_json(resp.text)

            if resp.status_code >= 400:
                return False, f"{resp.status_code} - {payload}"

            token = _safe_str(payload.get("access_token"))

            if not token:
                return False, "Sem access_token"

            payload["created_at"] = int(time.time())

            self.store.save(self.user_key, payload)

            return True, "Token salvo"

        except Exception as e:
            return False, str(e)

    # =========================
    # CALLBACK
    # =========================
    def handle_oauth_callback(self) -> Dict[str, str]:
        qp = st.query_params

        if "code" not in qp:
            return {"status": "idle", "message": ""}

        code = _safe_str(qp.get("code"))

        ok, msg = self.exchange_code_for_token(code)

        # limpa params
        try:
            del st.query_params["code"]
            del st.query_params["state"]
        except Exception:
            pass

        if ok:
            return {"status": "success", "message": "Conectado com sucesso"}

        return {"status": "error", "message": msg}

    # =========================
    # TOKEN USO
    # =========================
    def get_token(self) -> Tuple[bool, str]:
        data = self.store.get(self.user_key) or {}

        token = _safe_str(data.get("access_token"))

        if not token:
            return False, "Token inválido"

        return True, token
