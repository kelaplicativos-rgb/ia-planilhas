from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple
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


def _safe_str(value: object) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, list):
            return str(value[0] if value else "").strip()
        return str(value).strip()
    except Exception:
        return ""


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
        qp_user = ""
        try:
            qp_user = _safe_str(st.query_params.get("bi"))
        except Exception:
            qp_user = ""

        self.user_key = _safe_str(qp_user or user_key or "default") or "default"
        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings.token_store_path)
        self._client = httpx.Client(timeout=30.0)

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})

        return BlingSettings(
            client_id=_safe_str(cfg.get("client_id")),
            client_secret=_safe_str(cfg.get("client_secret")),
            redirect_uri=_safe_str(cfg.get("redirect_uri")),
            authorize_url=_safe_str(cfg.get("authorize_url"))
            or "https://www.bling.com.br/Api/v3/oauth/authorize",
            token_url=_safe_str(cfg.get("token_url"))
            or "https://www.bling.com.br/Api/v3/oauth/token",
            revoke_url=_safe_str(cfg.get("revoke_url"))
            or "https://www.bling.com.br/Api/v3/oauth/revoke",
            api_base_url=_safe_str(cfg.get("api_base_url"))
            or "https://api.bling.com.br/Api/v3",
            token_store_path=_safe_str(cfg.get("token_store_path"))
            or "bling_app_zero/output/bling_tokens.json",
            stock_write_path=_safe_str(cfg.get("stock_write_path")) or "/estoques",
        )

    def is_configured(self) -> bool:
        return bool(
            self.settings.client_id
            and self.settings.client_secret
            and self.settings.redirect_uri
        )

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _clear_oauth_query_params(self) -> None:
        """
        Remove apenas parâmetros de OAuth, preservando bi/user_key.
        """
        try:
            qp = st.query_params
            for key in ["code", "state", "error", "error_description"]:
                try:
                    del qp[key]
                except Exception:
                    pass
        except Exception:
            pass

    def _normalize_token_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        data["created_at"] = int(time.time())
        return data

    # =========================
    # AUTH URL
    # =========================
    def generate_auth_url(self) -> str:
        if not self.is_configured():
            return ""

        state = secrets.token_urlsafe(24)
        st.session_state["_oauth_state"] = state
        st.session_state["_oauth_pending_user_key"] = self.user_key

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
        }

        return f"{self.settings.authorize_url}?{urlencode(params)}"

    # alias para compatibilidade com código legado
    def build_authorize_url(self) -> str:
        return self.generate_auth_url()

    # =========================
    # TOKEN
    # =========================
    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        code = _safe_str(code)
        if not code:
            return False, "Código OAuth ausente"

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

            resp = self._client.post(
                self.settings.token_url,
                headers=headers,
                data=data,
            )

            content_type = _safe_str(resp.headers.get("content-type")).lower()
            payload = resp.json() if "application/json" in content_type else {}

            if resp.status_code >= 400:
                return False, json.dumps(payload, ensure_ascii=False) or resp.text

            payload = self._normalize_token_payload(payload)
            salvo = self.store.save(self.user_key, payload)

            if not salvo:
                return False, "Token recebido, mas não foi salvo"

            return True, "Token obtido com sucesso"

        except Exception as e:
            return False, str(e)

    def refresh_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key) or {}
        refresh_token = _safe_str(current.get("refresh_token"))

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

            resp = self._client.post(
                self.settings.token_url,
                headers=headers,
                data=data,
            )

            content_type = _safe_str(resp.headers.get("content-type")).lower()
            payload = resp.json() if "application/json" in content_type else {}

            if resp.status_code >= 400:
                return False, json.dumps(payload, ensure_ascii=False) or resp.text

            payload = self._normalize_token_payload(payload)
            salvo = self.store.save(self.user_key, payload)

            if not salvo:
                return False, "Token renovado, mas não foi salvo"

            return True, "Token renovado"

        except Exception as e:
            return False, str(e)

    # =========================
    # CALLBACK
    # =========================
    def handle_oauth_callback(self) -> Dict[str, str]:
        try:
            qp = st.query_params
        except Exception:
            qp = {}

        has_code = "code" in qp
        has_error = "error" in qp

        if not has_code and not has_error:
            return {"status": "idle", "message": ""}

        if has_error:
            msg = _safe_str(qp.get("error_description")) or _safe_str(qp.get("error")) or "Erro ao autenticar no Bling"
            self._clear_oauth_query_params()
            st.session_state["_oauth_state"] = ""
            return {"status": "error", "message": msg}

        code = _safe_str(qp.get("code"))
        incoming_state = _safe_str(qp.get("state"))
        saved_state = _safe_str(st.session_state.get("_oauth_state"))

        if not code:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Código OAuth ausente"}

        if saved_state and incoming_state and incoming_state != saved_state:
            self._clear_oauth_query_params()
            st.session_state["_oauth_state"] = ""
            return {"status": "error", "message": "State inválido"}

        ok, msg = self.exchange_code_for_token(code)

        self._clear_oauth_query_params()
        st.session_state["_oauth_state"] = ""

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
        token = _safe_str(current.get("access_token"))

        if not token:
            return False, "Token inválido"

        if not self.store.is_expired(current):
            return True, token

        ok, msg = self.refresh_access_token()
        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key) or {}
        token = _safe_str(refreshed.get("access_token"))

        return (True, token) if token else (False, "Token inválido após refresh")

    def has_valid_token(self) -> bool:
        ok, _ = self.get_valid_access_token()
        return bool(ok)

    def get_connection_status(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "configured": False,
                "connected": False,
                "message": "Credenciais do Bling não configuradas",
            }

        current = self.store.get(self.user_key) or {}
        access_token = _safe_str(current.get("access_token"))

        if not access_token:
            return {
                "configured": True,
                "connected": False,
                "message": "Conta ainda não conectada",
            }

        if self.store.is_expired(current):
            ok, msg = self.refresh_access_token()
            if not ok:
                return {
                    "configured": True,
                    "connected": False,
                    "message": msg,
                }

        return {
            "configured": True,
            "connected": True,
            "message": "Conta conectada",
            }
