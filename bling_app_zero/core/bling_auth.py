from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore


# =========================
# HELPERS
# =========================
def _safe_json_load(text: str) -> Dict[str, Any]:
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
    revoke_url: str
    api_base_url: str
    token_store_path: str
    stock_write_path: str


# =========================
# AUTH MANAGER
# =========================
class BlingAuthManager:
    def __init__(self, user_key: str = "default") -> None:
        qp_user = st.query_params.get("bi")

        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""

        self.user_key = str(qp_user or user_key or "default").strip()

        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings.token_store_path)

        # 🔥 CLIENT REUTILIZADO
        self._client = httpx.Client(timeout=30.0)

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})

        return BlingSettings(
            client_id=str(cfg.get("client_id", "")).strip(),
            client_secret=str(cfg.get("client_secret", "")).strip(),
            redirect_uri=str(cfg.get("redirect_uri", "")).strip(),
            authorize_url=str(cfg.get("authorize_url", "https://www.bling.com.br/Api/v3/oauth/authorize")).strip(),
            token_url=str(cfg.get("token_url", "https://www.bling.com.br/Api/v3/oauth/token")).strip(),
            revoke_url=str(cfg.get("revoke_url", "https://www.bling.com.br/Api/v3/oauth/revoke")).strip(),
            api_base_url=str(cfg.get("api_base_url", "https://api.bling.com.br/Api/v3")).strip(),
            token_store_path=str(cfg.get("token_store_path", "bling_app_zero/output/bling_tokens.json")).strip(),
            stock_write_path=str(cfg.get("stock_write_path", "/estoques")).strip(),
        )

    def is_configured(self) -> bool:
        return bool(self.settings.client_id and self.settings.client_secret and self.settings.redirect_uri)

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _clear_oauth_query_params(self) -> None:
        try:
            st.query_params.clear()
        except Exception:
            pass

    # =========================
    # AUTH URL
    # =========================
    def generate_auth_url(self) -> str:
        state = secrets.token_urlsafe(16)

        # 🔥 salva no session_state (sem arquivo)
        st.session_state["_oauth_state"] = state

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
        }

        return f"{self.settings.authorize_url}?{urlencode(params)}"

    # =========================
    # TOKEN
    # =========================
    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        try:
            headers = {
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.redirect_uri,
            }

            resp = self._client.post(self.settings.token_url, headers=headers, data=data)

            payload = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}

            if resp.status_code >= 400:
                return False, str(payload)

            payload["created_at"] = int(time.time())

            self.store.save(self.user_key, payload)

            return True, "Token obtido com sucesso"

        except Exception as e:
            return False, str(e)

    def refresh_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key) or {}
        refresh_token = current.get("refresh_token")

        if not refresh_token:
            return False, "Refresh token ausente"

        try:
            headers = {
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }

            resp = self._client.post(self.settings.token_url, headers=headers, data=data)

            payload = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}

            if resp.status_code >= 400:
                return False, str(payload)

            payload["created_at"] = int(time.time())

            self.store.save(self.user_key, payload)

            return True, "Token renovado"

        except Exception as e:
            return False, str(e)

    # =========================
    # CALLBACK
    # =========================
    def handle_oauth_callback(self) -> Dict[str, str]:
        qp = st.query_params

        if "code" not in qp and "error" not in qp:
            return {"status": "idle", "message": ""}

        if "error" in qp:
            msg = str(qp.get("error_description", qp.get("error", "")))
            self._clear_oauth_query_params()
            return {"status": "error", "message": msg}

        code = str(qp.get("code", "")).strip()
        incoming_state = str(qp.get("state", "")).strip()

        saved_state = str(st.session_state.get("_oauth_state", "")).strip()

        if not saved_state or incoming_state != saved_state:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido"}

        ok, msg = self.exchange_code_for_token(code)

        self._clear_oauth_query_params()
        st.session_state["_oauth_state"] = None

        if not ok:
            return {"status": "error", "message": msg}

        return {"status": "success", "message": "Conta conectada com sucesso"}

    # =========================
    # TOKEN VÁLIDO
    # =========================
    def get_valid_access_token(self) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Bling não configurado"

        current = self.store.get(self.user_key) or {}

        token = str(current.get("access_token", "")).strip()

        if not token:
            return False, "Token inválido"

        if not self.store.is_expired(current):
            return True, token

        ok, msg = self.refresh_access_token()

        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key) or {}
        token = str(refreshed.get("access_token", "")).strip()

        return (True, token) if token else (False, "Token inválido após refresh")
