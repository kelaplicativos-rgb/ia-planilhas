from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple
from urllib.parse import quote, urlencode

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore
from bling_app_zero.core.bling_user_session import clear_pending_oauth_user


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


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = _safe_str(value)
        if text:
            return text
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
    stock_write_path: str


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
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
        )

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})

        settings = BlingSettings(
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

        try:
            st.session_state["_bling_debug_redirect_uri_runtime"] = settings.redirect_uri
            st.session_state["_bling_debug_authorize_url_runtime"] = settings.authorize_url
        except Exception:
            pass

        return settings

    def is_configured(self) -> bool:
        return bool(
            self.settings.client_id
            and self.settings.client_secret
            and self.settings.redirect_uri
        )

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _oauth_session_key(self, suffix: str) -> str:
        return f"_oauth_{suffix}_{self.user_key}"

    def _save_state(self, state: str) -> None:
        st.session_state["_oauth_state"] = state
        st.session_state[self._oauth_session_key("state")] = state
        st.session_state["_oauth_pending_user_key"] = self.user_key
        st.session_state[self._oauth_session_key("pending_user_key")] = self.user_key
        st.session_state[self._oauth_session_key("started_at")] = int(time.time())

    def _get_saved_state(self) -> str:
        global_state = _safe_str(st.session_state.get("_oauth_state"))
        scoped_state = _safe_str(st.session_state.get(self._oauth_session_key("state")))
        return scoped_state or global_state

    def _clear_saved_state(self) -> None:
        st.session_state["_oauth_state"] = ""
        for key in [
            self._oauth_session_key("state"),
            self._oauth_session_key("pending_user_key"),
            self._oauth_session_key("started_at"),
        ]:
            st.session_state.pop(key, None)

    def _clear_oauth_query_params(self) -> None:
        try:
            qp = st.query_params
            for key in ["code", "state", "error", "error_description", "bling_callback"]:
                try:
                    del qp[key]
                except Exception:
                    pass
        except Exception:
            pass

    def _normalize_token_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}

        if not _safe_str(data.get("token_type")):
            data["token_type"] = "Bearer"

        expires_in = _safe_int(data.get("expires_in"), 0)
        if expires_in <= 0:
            data["expires_in"] = 3600

        if not _safe_str(data.get("refresh_token")):
            existing = self.store.get(self.user_key) or {}
            previous_refresh = _safe_str(existing.get("refresh_token"))
            if previous_refresh:
                data["refresh_token"] = previous_refresh

        data["created_at"] = int(time.time())
        return data

    def _extract_response_payload(self, resp: httpx.Response) -> Dict[str, Any]:
        content_type = _safe_str(resp.headers.get("content-type")).lower()
        if "application/json" in content_type:
            try:
                data = resp.json()
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return _safe_json_load(resp.text)

    def _extract_error_message(
        self,
        resp: httpx.Response,
        payload: Dict[str, Any],
    ) -> str:
        if isinstance(payload, dict) and payload:
            mensagem = _first_non_empty(
                payload.get("error_description"),
                payload.get("error"),
                payload.get("message"),
                payload.get("mensagem"),
                payload.get("descricao"),
                payload.get("description"),
            )
            if mensagem:
                return f"{resp.status_code} - {mensagem}"

            try:
                return f"{resp.status_code} - {json.dumps(payload, ensure_ascii=False)}"
            except Exception:
                pass

        texto = _safe_str(resp.text)
        if texto:
            return f"{resp.status_code} - {texto}"

        return f"{resp.status_code} - erro ao comunicar com o Bling"

    def _request_token(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        attempts = [
            {
                "headers": {
                    "Authorization": self._basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                "data": data,
            },
            {
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                "data": {
                    **data,
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                },
            },
        ]

        last_error = "Falha ao obter token"

        for attempt in attempts:
            try:
                resp = self._client.post(
                    self.settings.token_url,
                    headers=attempt["headers"],
                    data=attempt["data"],
                )
                payload = self._extract_response_payload(resp)

                if resp.status_code >= 400:
                    last_error = self._extract_error_message(resp, payload)
                    continue

                if not _safe_str(payload.get("access_token")):
                    last_error = (
                        "Resposta do Bling sem access_token. "
                        f"Payload: {json.dumps(payload, ensure_ascii=False)}"
                    )
                    continue

                return True, payload, ""

            except Exception as e:
                last_error = str(e)

        return False, {}, last_error

    def generate_auth_url(self) -> str:
        if not self.is_configured():
            try:
                st.session_state["_bling_debug_auth_error"] = (
                    "OAuth não configurado: client_id/client_secret/redirect_uri ausentes."
                )
                st.session_state["_bling_debug_auth_url_final"] = ""
            except Exception:
                pass
            return ""

        redirect_uri = _safe_str(self.settings.redirect_uri)
        if not redirect_uri:
            try:
                st.session_state["_bling_debug_auth_error"] = "redirect_uri vazio em runtime."
                st.session_state["_bling_debug_auth_url_final"] = ""
            except Exception:
                pass
            return ""

        state = secrets.token_urlsafe(24)
        self._save_state(state)

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        auth_url = f"{self.settings.authorize_url}?{urlencode(params)}"

        if "redirect_uri=" not in auth_url:
            auth_url = (
                f"{self.settings.authorize_url}"
                f"?response_type=code"
                f"&client_id={quote(self.settings.client_id, safe='')}"
                f"&redirect_uri={quote(redirect_uri, safe='')}"
                f"&state={quote(state, safe='')}"
            )

        try:
            st.session_state["_bling_debug_auth_error"] = ""
            st.session_state["_bling_debug_auth_state"] = state
            st.session_state["_bling_debug_auth_url_final"] = auth_url
            st.session_state["_bling_debug_redirect_uri_raw"] = redirect_uri
            st.session_state["_bling_debug_redirect_uri_encoded"] = quote(
                redirect_uri,
                safe="",
            )
        except Exception:
            pass

        return auth_url

    def build_authorize_url(self) -> str:
        return self.generate_auth_url()

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        code = _safe_str(code)
        if not code:
            return False, "Código OAuth ausente"

        if not self.is_configured():
            return False, "Credenciais do Bling não configuradas"

        ok, payload, error = self._request_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.redirect_uri,
            }
        )
        if not ok:
            return False, error

        payload = self._normalize_token_payload(payload)
        salvo = self.store.save(self.user_key, payload)
        if not salvo:
            return False, "Token recebido, mas não foi salvo"

        return True, "Token obtido com sucesso"

    def refresh_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key) or {}
        refresh_token = _safe_str(current.get("refresh_token"))
        if not refresh_token:
            return False, "Refresh token ausente"

        if not self.is_configured():
            return False, "Credenciais do Bling não configuradas"

        ok, payload, error = self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "redirect_uri": self.settings.redirect_uri,
            }
        )
        if not ok:
            try:
                self.store.delete(self.user_key)
            except Exception:
                pass
            return False, error

        payload = self._normalize_token_payload(payload)
        salvo = self.store.save(self.user_key, payload)
        if not salvo:
            return False, "Token renovado, mas não foi salvo"

        return True, "Token renovado"

    def revoke_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key) or {}
        access_token = _safe_str(current.get("access_token"))
        if not access_token:
            return False, "Nenhum token para revogar"

        if not self.is_configured():
            return False, "Credenciais do Bling não configuradas"

        try:
            headers = {
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            data = {"token": access_token}

            resp = self._client.post(
                self.settings.revoke_url,
                headers=headers,
                data=data,
            )
            payload = self._extract_response_payload(resp)

            if resp.status_code >= 400:
                return False, self._extract_error_message(resp, payload)

            try:
                self.store.delete(self.user_key)
            except Exception:
                pass

            return True, "Token revogado com sucesso"
        except Exception as e:
            return False, str(e)

    def handle_oauth_callback(self) -> Dict[str, str]:
        try:
            qp = st.query_params
        except Exception:
            qp = {}

        has_code = "code" in qp
        has_error = "error" in qp
        has_callback_flag = _safe_str(qp.get("bling_callback")) == "1"

        if not has_code and not has_error:
            return {"status": "idle", "message": ""}

        if not has_callback_flag and (has_code or has_error):
            return {"status": "idle", "message": ""}

        if has_error:
            msg = (
                _safe_str(qp.get("error_description"))
                or _safe_str(qp.get("error"))
                or "Erro ao autenticar no Bling"
            )
            self._clear_oauth_query_params()
            self._clear_saved_state()
            clear_pending_oauth_user()
            return {"status": "error", "message": msg}

        code = _safe_str(qp.get("code"))
        incoming_state = _safe_str(qp.get("state"))
        saved_state = self._get_saved_state()

        if not code:
            self._clear_oauth_queryParams = None
            self._clear_oauth_query_params()
            self._clear_saved_state()
            return {"status": "error", "message": "Código OAuth ausente"}

        if saved_state and incoming_state and incoming_state != saved_state:
            self._clear_oauth_query_params()
            self._clear_saved_state()
            clear_pending_oauth_user()
            return {"status": "error", "message": "State inválido"}

        ok, msg = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()
        self._clear_saved_state()

        if not ok:
            clear_pending_oauth_user()
            return {"status": "error", "message": msg}

        clear_pending_oauth_user()
        return {"status": "success", "message": "Conta conectada com sucesso"}

    def get_valid_access_token(self) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "Bling não configurado"

        current = self.store.get(self.user_key) or {}
        token = _safe_str(current.get("access_token"))
        if not token:
            return False, "Token inválido"

        try:
            expired = bool(self.store.is_expired(current))
        except Exception:
            expired = True

        if not expired:
            return True, token

        ok, msg = self.refresh_access_token()
        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key) or {}
        token = _safe_str(refreshed.get("access_token"))
        return (True, token) if token else (False, "Token inválido após refresh")

    def get_token(self) -> Tuple[bool, str]:
        return self.get_valid_access_token()

    def has_valid_token(self) -> bool:
        ok, _ = self.get_valid_access_token()
        return bool(ok)

    def get_connection_status(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "configured": False,
                "connected": False,
                "message": "Credenciais do Bling não configuradas",
                "user_key": self.user_key,
            }

        current = self.store.get(self.user_key) or {}
        access_token = _safe_str(current.get("access_token"))

        if not access_token:
            return {
                "configured": True,
                "connected": False,
                "message": "Conta ainda não conectada",
                "user_key": self.user_key,
            }

        try:
            expired = bool(self.store.is_expired(current))
        except Exception:
            expired = True

        if expired:
            ok, msg = self.refresh_access_token()
            if not ok:
                return {
                    "configured": True,
                    "connected": False,
                    "message": msg,
                    "user_key": self.user_key,
                }

        refreshed = self.store.get(self.user_key) or {}
        created_at = _safe_int(refreshed.get("created_at"), 0)
        expires_in = _safe_int(refreshed.get("expires_in"), 0)

        return {
            "configured": True,
            "connected": True,
            "message": "Conta conectada",
            "user_key": self.user_key,
            "created_at": created_at,
            "expires_in": expires_in,
        }

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
