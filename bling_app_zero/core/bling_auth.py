from __future__ import annotations

import base64
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore


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
        self.user_key = user_key
        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings.token_store_path)

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})

        client_id = str(cfg.get("client_id", "")).strip()
        client_secret = str(cfg.get("client_secret", "")).strip()
        redirect_uri = str(cfg.get("redirect_uri", "")).strip()

        if not client_id or not client_secret or not redirect_uri:
            return BlingSettings(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                authorize_url=str(cfg.get("authorize_url", "https://api.bling.com.br/Api/v3/oauth/authorize")).strip(),
                token_url=str(cfg.get("token_url", "https://api.bling.com.br/Api/v3/oauth/token")).strip(),
                revoke_url=str(cfg.get("revoke_url", "https://api.bling.com.br/Api/v3/oauth/revoke")).strip(),
                api_base_url=str(cfg.get("api_base_url", "https://api.bling.com.br/Api/v3")).strip(),
                token_store_path=str(cfg.get("token_store_path", "bling_app_zero/output/bling_tokens.json")).strip(),
            )

        return BlingSettings(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            authorize_url=str(cfg.get("authorize_url", "https://api.bling.com.br/Api/v3/oauth/authorize")).strip(),
            token_url=str(cfg.get("token_url", "https://api.bling.com.br/Api/v3/oauth/token")).strip(),
            revoke_url=str(cfg.get("revoke_url", "https://api.bling.com.br/Api/v3/oauth/revoke")).strip(),
            api_base_url=str(cfg.get("api_base_url", "https://api.bling.com.br/Api/v3")).strip(),
            token_store_path=str(cfg.get("token_store_path", "bling_app_zero/output/bling_tokens.json")).strip(),
        )

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("utf-8")
        return f"Basic {encoded}"

    def _assert_configured(self) -> None:
        if not self.settings.client_id or not self.settings.client_secret or not self.settings.redirect_uri:
            raise RuntimeError(
                "Integração Bling não configurada. Preencha client_id, client_secret e redirect_uri em st.secrets['bling']."
            )

    def build_authorize_url(self, force_reauth: bool = False) -> str:
        self._assert_configured()

        state = secrets.token_hex(24)
        st.session_state["bling_oauth_state"] = state
        st.session_state["bling_oauth_state_created_at"] = int(time.time())

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "state": state,
        }

        # Alguns provedores aceitam prompt/force; se o Bling ignorar, não quebra.
        if force_reauth:
            params["prompt"] = "consent"

        return f"{self.settings.authorize_url}?{urlencode(params)}"

    def handle_oauth_callback(self) -> Dict[str, str]:
        query_params = st.query_params

        if "code" not in query_params and "error" not in query_params:
            return {"status": "idle", "message": ""}

        if "error" in query_params:
            message = str(query_params.get("error_description", query_params.get("error", "Autorização negada.")))
            self._clear_oauth_query_params()
            return {"status": "error", "message": f"Falha na autorização do Bling: {message}"}

        code = str(query_params.get("code", "")).strip()
        incoming_state = str(query_params.get("state", "")).strip()
        expected_state = str(st.session_state.get("bling_oauth_state", "")).strip()
        created_at = int(st.session_state.get("bling_oauth_state_created_at", 0) or 0)

        if not code:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Callback do Bling sem code."}

        if not expected_state or incoming_state != expected_state:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido na autenticação com o Bling."}

        if created_at and (int(time.time()) - created_at) > 15 * 60:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State expirado. Gere uma nova autenticação."}

        ok, payload_or_error = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()

        if not ok:
            return {"status": "error", "message": payload_or_error}

        self.try_fill_company_name()
        return {"status": "success", "message": "Conta Bling conectada com sucesso."}

    def _clear_oauth_query_params(self) -> None:
        try:
            st.query_params.clear()
        except Exception:
            pass

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        self._assert_configured()

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "enable-jwt": "1",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.token_url, headers=headers, data=data)
                content_type = resp.headers.get("content-type", "")
                payload = resp.json() if "application/json" in content_type else {"raw": resp.text}

            if resp.status_code >= 400:
                return False, f"Erro ao trocar code por token: HTTP {resp.status_code} | {payload}"

            self.store.save_token_payload(payload, user_key=self.user_key)
            return True, "ok"

        except Exception as exc:
            return False, f"Erro ao autenticar com o Bling: {exc}"

    def refresh_access_token(self) -> Tuple[bool, str]:
        self._assert_configured()

        current = self.store.get(self.user_key)
        refresh_token = (current or {}).get("refresh_token", "")

        if not refresh_token:
            return False, "Refresh token não encontrado. Reconecte a conta Bling."

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "enable-jwt": "1",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.token_url, headers=headers, data=data)
                content_type = resp.headers.get("content-type", "")
                payload = resp.json() if "application/json" in content_type else {"raw": resp.text}

            if resp.status_code >= 400:
                return False, f"Erro ao renovar token: HTTP {resp.status_code} | {payload}"

            self.store.save_token_payload(payload, user_key=self.user_key)
            return True, "Token renovado com sucesso."

        except Exception as exc:
            return False, f"Falha ao renovar token do Bling: {exc}"

    def get_valid_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key)

        if not current:
            return False, "Conta Bling ainda não conectada."

        if not self.store.is_expired(current):
            return True, str(current.get("access_token", ""))

        ok, msg = self.refresh_access_token()
        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key)
        access_token = str((refreshed or {}).get("access_token", ""))
        if not access_token:
            return False, "Token renovado, mas access_token não foi encontrado."

        return True, access_token

    def revoke_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key)
        if not current:
            return True, "Conta já estava desconectada."

        access_token = str(current.get("access_token", "")).strip()
        if not access_token:
            return True, "Conta já estava desconectada."

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "token": access_token,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.revoke_url, headers=headers, data=data)

            if resp.status_code >= 400:
                return False, f"Erro ao revogar token no Bling: HTTP {resp.status_code} | {resp.text}"

            return True, "Token revogado no Bling."
        except Exception as exc:
            return False, f"Falha ao revogar token no Bling: {exc}"

    def disconnect(self) -> Tuple[bool, str]:
        revoke_ok, revoke_msg = self.revoke_token()
        self.store.delete(self.user_key)

        if revoke_ok:
            return True, "Conta Bling desconectada com sucesso."
        return False, revoke_msg

    def get_connection_status(self) -> Dict[str, Optional[str]]:
        current = self.store.get(self.user_key) or {}
        connected = bool(current.get("access_token"))

        return {
            "connected": connected,
            "company_name": current.get("company_name"),
            "last_auth_at": current.get("last_auth_at"),
            "expires_at": current.get("expires_at"),
        }

    def try_fill_company_name(self) -> None:
        ok, token_or_msg = self.get_valid_access_token()
        if not ok:
            return

        headers = {
            "Authorization": f"Bearer {token_or_msg}",
            "Accept": "application/json",
            "enable-jwt": "1",
        }

        candidate_paths = [
            f"{self.settings.api_base_url}/empresas/me",
            f"{self.settings.api_base_url}/empresa",
            f"{self.settings.api_base_url}/conta",
        ]

        with httpx.Client(timeout=20.0) as client:
            for url in candidate_paths:
                try:
                    resp = client.get(url, headers=headers)
                    if resp.status_code >= 400:
                        continue
                    data = resp.json()
                    company_name = self._extract_company_name(data)
                    if company_name:
                        self.store.update_company_name(company_name, user_key=self.user_key)
                        return
                except Exception:
                    continue

    @staticmethod
    def _extract_company_name(payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("nome", "razaoSocial", "fantasia", "empresa", "descricao"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            for value in payload.values():
                found = BlingAuthManager._extract_company_name(value)
                if found:
                    return found

        if isinstance(payload, list):
            for item in payload:
                found = BlingAuthManager._extract_company_name(item)
                if found:
                    return found

        return None
