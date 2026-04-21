from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import quote

import httpx
import streamlit as st


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


def _format_ts(ts: int | float | None) -> str:
    try:
        if not ts:
            return ""
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _log(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
    except Exception:
        pass


def _clear_oauth_query_params() -> None:
    for key in ("code", "state", "error", "error_description"):
        try:
            st.query_params.pop(key, None)
        except Exception:
            try:
                del st.query_params[key]
            except Exception:
                pass


class BlingTokenStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def _save(self, data: dict) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self, user_key: str, payload: dict) -> None:
        data = self._load()
        data[user_key] = payload
        self._save(data)

    def get(self, user_key: str) -> dict:
        data = self._load()
        token = data.get(user_key, {})
        return token if isinstance(token, dict) else {}

    def delete(self, user_key: str) -> None:
        data = self._load()
        data.pop(user_key, None)
        self._save(data)

    def update(self, user_key: str, values: dict) -> dict:
        data = self._load()
        current = data.get(user_key, {})
        if not isinstance(current, dict):
            current = {}
        current.update(values)
        data[user_key] = current
        self._save(data)
        return current

    def is_expired(self, token: dict, safety_seconds: int = 120) -> bool:
        if not isinstance(token, dict) or not token:
            return True

        created = int(token.get("created_at", 0) or 0)
        expires = int(token.get("expires_in", 0) or 0)

        if created <= 0 or expires <= 0:
            return True

        return time.time() >= (created + expires - safety_seconds)


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
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _headers_form(self) -> Dict[str, str]:
        return {
            "Authorization": self._basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

    def generate_auth_url(self) -> str:
        state = secrets.token_urlsafe(24)
        st.session_state["_bling_oauth_state"] = state
        st.session_state["_bling_oauth_user_key"] = self.user_key

        return (
            f"{self.settings.authorize_url}"
            f"?response_type=code"
            f"&client_id={self.settings.client_id}"
            f"&redirect_uri={quote(self.settings.redirect_uri)}"
            f"&state={state}"
        )

    def exchange_code_for_token(self, code: str) -> Tuple[bool, dict]:
        data = {
            "grant_type": "authorization_code",
            "code": _safe_str(code),
            "redirect_uri": self.settings.redirect_uri,
        }

        try:
            response = self.client.post(
                self.settings.token_url,
                headers=self._headers_form(),
                data=data,
            )
            payload = _safe_json_dict(response.text)
        except Exception as exc:
            return False, {"error": "request_error", "error_description": str(exc)}

        if response.status_code >= 400 or "access_token" not in payload:
            return False, payload or {
                "error": "token_exchange_failed",
                "error_description": f"HTTP {response.status_code}",
            }

        payload["created_at"] = int(time.time())
        payload["last_auth_at"] = int(time.time())
        self.store.save(self.user_key, payload)
        _log("OAuth do Bling concluído com sucesso.", nivel="INFO")
        return True, payload

    def refresh_access_token(self) -> Tuple[bool, str]:
        token = self.store.get(self.user_key)
        refresh_token = _safe_str(token.get("refresh_token"))

        if not refresh_token:
            return False, "Refresh token não encontrado."

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = self.client.post(
                self.settings.token_url,
                headers=self._headers_form(),
                data=data,
            )
            payload = _safe_json_dict(response.text)
        except Exception as exc:
            return False, f"Falha ao atualizar token: {exc}"

        if response.status_code >= 400 or "access_token" not in payload:
            return False, json.dumps(payload, ensure_ascii=False)

        payload["created_at"] = int(time.time())
        payload["last_auth_at"] = int(token.get("last_auth_at", time.time()) or time.time())
        if not payload.get("refresh_token"):
            payload["refresh_token"] = refresh_token

        merged = token.copy()
        merged.update(payload)
        self.store.save(self.user_key, merged)
        _log("Token do Bling renovado com sucesso.", nivel="INFO")
        return True, _safe_str(merged.get("access_token"))

    def get_token_data(self) -> dict:
        return self.store.get(self.user_key)

    def get_valid_access_token(self) -> Tuple[bool, str]:
        token = self.get_token_data()
        access_token = _safe_str(token.get("access_token"))

        if not token or not access_token:
            return False, "Conta do Bling ainda não conectada."

        if self.store.is_expired(token):
            ok_refresh, token_or_error = self.refresh_access_token()
            if not ok_refresh:
                return False, token_or_error
            return True, token_or_error

        return True, access_token

    def revoke_token(self) -> Tuple[bool, str]:
        token = self.get_token_data()
        refresh_token = _safe_str(token.get("refresh_token")) or _safe_str(token.get("access_token"))

        if not refresh_token:
            self.store.delete(self.user_key)
            return True, "Nenhum token restante para revogar."

        data = {"token": refresh_token}

        try:
            response = self.client.post(
                self.settings.revoke_url,
                headers=self._headers_form(),
                data=data,
            )
        except Exception as exc:
            return False, f"Falha ao revogar token: {exc}"

        self.store.delete(self.user_key)

        if response.status_code >= 400:
            return False, f"Falha ao revogar token. HTTP {response.status_code}"

        return True, "Token revogado com sucesso."

    def process_callback_from_query_params(self) -> Tuple[bool, str]:
        error = _query_param("error")
        if error:
            description = _query_param("error_description")
            _clear_oauth_query_params()
            return False, description or error

        code = _query_param("code")
        state = _query_param("state")

        if not code:
            return False, ""

        expected_state = _safe_str(st.session_state.get("_bling_oauth_state"))
        expected_user_key = _safe_str(st.session_state.get("_bling_oauth_user_key") or self.user_key)

        if expected_state and state and expected_state != state:
            _clear_oauth_query_params()
            _log("State OAuth do Bling inválido.", nivel="ERRO")
            return False, "Falha de segurança no retorno OAuth do Bling."

        if expected_user_key and expected_user_key != self.user_key:
            self.user_key = expected_user_key

        ok, payload = self.exchange_code_for_token(code)
        _clear_oauth_query_params()

        if not ok:
            return False, (
                _safe_str(payload.get("error_description"))
                or _safe_str(payload.get("message"))
                or json.dumps(payload, ensure_ascii=False)
            )

        return True, "Conta conectada com sucesso."

    def get_connection_status(self) -> dict:
        if not self.is_configured():
            return {
                "connected": False,
                "conectado": False,
                "status": "OAuth não configurado",
                "company_name": "",
                "expires_at": "",
                "last_auth_at": "",
                "token_found": False,
            }

        token = self.get_token_data()
        token_found = bool(token)
        access_token = _safe_str(token.get("access_token"))
        expired = self.store.is_expired(token) if token_found else True

        connected = bool(access_token) and not expired
        status = "Conectado" if connected else ("Token expirado" if token_found else "Desconectado")

        created_at = int(token.get("created_at", 0) or 0)
        expires_in = int(token.get("expires_in", 0) or 0)
        expires_at = _format_ts(created_at + expires_in) if created_at and expires_in else ""

        return {
            "connected": connected,
            "conectado": connected,
            "status": status,
            "company_name": _safe_str(token.get("company_name")),
            "expires_at": expires_at,
            "last_auth_at": _format_ts(int(token.get("last_auth_at", 0) or 0)),
            "token_found": token_found,
        }


def obter_resumo_conexao(user_key: str = "default") -> dict:
    auth = BlingAuthManager(user_key=user_key)
    return auth.get_connection_status()


def usuario_conectado_bling(user_key: str = "default") -> bool:
    return bool(obter_resumo_conexao(user_key=user_key).get("conectado", False))


def tem_token_valido(user_key: str = "default") -> bool:
    auth = BlingAuthManager(user_key=user_key)
    ok, _ = auth.get_valid_access_token()
    return bool(ok)


def render_conectar_bling(
    user_key: str = "default",
    titulo: str = "Conectar com Bling",
) -> None:
    auth = BlingAuthManager(user_key=user_key)

    if not auth.is_configured():
        st.error("Integração OAuth do Bling não configurada em `.streamlit/secrets.toml`.")
        return

    callback_ok, callback_msg = auth.process_callback_from_query_params()
    if callback_msg:
        if callback_ok:
            st.success(callback_msg)
            st.rerun()
        else:
            st.error(callback_msg)

    status = auth.get_connection_status()

    if status.get("connected"):
        st.success("✅ Conta conectada ao Bling.")
        if status.get("expires_at"):
            st.caption(f"Expira em: {status['expires_at']}")
        if status.get("last_auth_at"):
            st.caption(f"Última autenticação: {status['last_auth_at']}")
        return

    url = auth.generate_auth_url()

    st.markdown(
        f"""
        <a href="{url}" target="_self">
            <button style="width:100%;padding:12px;background:#16a34a;color:white;border:none;border-radius:10px;font-weight:600;cursor:pointer;">
                {titulo}
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )


def processar_callback_bling(user_key: str = "default") -> tuple[bool, str]:
    auth = BlingAuthManager(user_key=user_key)
    return auth.process_callback_from_query_params()
