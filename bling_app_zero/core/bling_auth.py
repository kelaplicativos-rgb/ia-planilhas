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


class BlingAuthManager:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = user_key
        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings.token_store_path)

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})
        return BlingSettings(
            client_id=str(cfg.get("client_id", "")).strip(),
            client_secret=str(cfg.get("client_secret", "")).strip(),
            redirect_uri=str(cfg.get("redirect_uri", "")).strip(),
            authorize_url=str(
                cfg.get("authorize_url", "https://www.bling.com.br/Api/v3/oauth/authorize")
            ).strip(),
            token_url=str(
                cfg.get("token_url", "https://www.bling.com.br/Api/v3/oauth/token")
            ).strip(),
            revoke_url=str(
                cfg.get("revoke_url", "https://www.bling.com.br/Api/v3/oauth/revoke")
            ).strip(),
            api_base_url=str(
                cfg.get("api_base_url", "https://api.bling.com.br/Api/v3")
            ).strip(),
            token_store_path=str(
                cfg.get("token_store_path", "bling_app_zero/output/bling_tokens.json")
            ).strip(),
            stock_write_path=str(cfg.get("stock_write_path", "/estoques")).strip(),
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

    def build_authorize_url(self, force_reauth: bool = False) -> Optional[str]:
        if not self.is_configured():
            return None

        state = secrets.token_hex(24)
        st.session_state["bling_oauth_state"] = state
        st.session_state["bling_oauth_state_created_at"] = int(time.time())

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            # No Bling o redirect_uri pode ser opcional quando já está cadastrado,
            # mas enviá-lo aqui reduz ambiguidades entre ambiente local e produção.
            "redirect_uri": self.settings.redirect_uri,
            "state": state,
        }
        if force_reauth:
            params["prompt"] = "consent"

        return f"{self.settings.authorize_url}?{urlencode(params)}"

    def _clear_oauth_query_params(self) -> None:
        try:
            query_params = st.query_params
            for key in ("code", "state", "error", "error_description"):
                if key in query_params:
                    del query_params[key]
        except Exception:
            try:
                st.query_params.clear()
            except Exception:
                pass

    def handle_oauth_callback(self) -> Dict[str, str]:
        query_params = st.query_params
        if "code" not in query_params and "error" not in query_params:
            return {"status": "idle", "message": ""}

        if "error" in query_params:
            msg = str(
                query_params.get(
                    "error_description",
                    query_params.get("error", "Autorização negada."),
                )
            )
            self._clear_oauth_query_params()
            return {
                "status": "error",
                "message": f"Falha na autorização do Bling: {msg}",
            }

        if not self.is_configured():
            self._clear_oauth_query_params()
            return {
                "status": "error",
                "message": "OAuth recebido, mas a configuração do Bling ainda não está preenchida.",
            }

        code = str(query_params.get("code", "")).strip()
        incoming_state = str(query_params.get("state", "")).strip()
        expected_state = str(st.session_state.get("bling_oauth_state", "")).strip()
        created_at = int(st.session_state.get("bling_oauth_state_created_at", 0) or 0)

        if not code:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Callback sem authorization code."}

        if not expected_state or incoming_state != expected_state:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido na autenticação com o Bling."}

        if created_at and (int(time.time()) - created_at) > 15 * 60:
            self._clear_oauth_query_params()
            return {
                "status": "error",
                "message": "State expirado. Gere uma nova autenticação.",
            }

        ok, msg = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()
        if not ok:
            return {"status": "error", "message": msg}

        self._hydrate_company_name_from_jwt()
        return {"status": "success", "message": "Conta Bling conectada com sucesso."}

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "enable-jwt": "1",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            # No Bling é opcional quando já está cadastrado, mas manter igual ajuda
            # em homologação e em cenários com múltiplos ambientes.
            "redirect_uri": self.settings.redirect_uri,
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.token_url, headers=headers, data=data)
                payload = (
                    resp.json()
                    if "application/json" in resp.headers.get("content-type", "")
                    else {"raw": resp.text}
                )
                if resp.status_code >= 400:
                    return (
                        False,
                        f"Erro ao trocar code por token: HTTP {resp.status_code} | {payload}",
                    )
                self.store.save_token_payload(payload, user_key=self.user_key)
                return True, "OK"
        except Exception as exc:
            return False, f"Erro ao autenticar com o Bling: {exc}"

    def refresh_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key)
        refresh_token = (current or {}).get("refresh_token", "")
        if not refresh_token:
            return False, "Refresh token não encontrado. Reconecte a conta."

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
                payload = (
                    resp.json()
                    if "application/json" in resp.headers.get("content-type", "")
                    else {"raw": resp.text}
                )
                if resp.status_code >= 400:
                    return False, f"Erro ao renovar token: HTTP {resp.status_code} | {payload}"
                self.store.save_token_payload(payload, user_key=self.user_key)
                self._hydrate_company_name_from_jwt()
                return True, "Token renovado."
        except Exception as exc:
            return False, f"Falha ao renovar token: {exc}"

    def get_valid_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key)
        if not current:
            return False, "Conta Bling ainda não conectada."

        if not self.store.is_expired(current):
            token = str(current.get("access_token", "")).strip()
            return (True, token) if token else (False, "Access token ausente.")

        ok, msg = self.refresh_access_token()
        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key) or {}
        token = str(refreshed.get("access_token", "")).strip()
        return (
            (True, token)
            if token
            else (False, "Token renovado, mas access_token não foi encontrado.")
        )

    def revoke_token(self) -> Tuple[bool, str]:
        if not self.is_configured():
            return True, "Credenciais não configuradas; token local removido."

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
        data = {"token": access_token}

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.revoke_url, headers=headers, data=data)
                if resp.status_code >= 400:
                    return False, f"Erro ao revogar token: HTTP {resp.status_code} | {resp.text}"
                return True, "Token revogado no Bling."
        except Exception as exc:
            return False, f"Falha ao revogar token: {exc}"

    def disconnect(self) -> Tuple[bool, str]:
        revoke_ok, revoke_msg = self.revoke_token()
        self.store.delete(self.user_key)
        if revoke_ok:
            return True, "Conta Bling desconectada com sucesso."
        return False, revoke_msg

    def _decode_jwt_payload(self, token: str) -> Dict[str, Any]:
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return {}
            payload = parts[1]
            padding = "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload + padding)
            data = json.loads(decoded.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _hydrate_company_name_from_jwt(self) -> None:
        current = self.store.get(self.user_key) or {}
        token = str(current.get("access_token", "")).strip()
        if not token:
            return

        payload = self._decode_jwt_payload(token)
        for key in (
            "company_name",
            "empresa",
            "empresa_nome",
            "organization_name",
            "username",
            "sub",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                self.store.update_company_name(value.strip(), user_key=self.user_key)
                return

    def get_connection_status(self) -> Dict[str, Optional[str]]:
        current = self.store.get(self.user_key) or {}
        connected = bool(current.get("access_token"))
        return {
            "connected": connected,
            "company_name": current.get("company_name"),
            "last_auth_at": current.get("last_auth_at"),
            "expires_at": current.get("expires_at"),
        }
