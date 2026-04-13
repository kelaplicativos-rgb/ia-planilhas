from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
import streamlit as st

try:
    from bling_app_zero.services.bling.bling_token_store import BlingTokenStore
except ImportError:
    from bling_app_zero.core.bling_token_store import BlingTokenStore


STATE_PATH = Path("bling_app_zero/output/oauth_state.json")
STATE_TTL_SECONDS = 15 * 60


def _safe_str(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _read_state_file() -> Dict[str, Dict[str, Any]]:
    try:
        if not STATE_PATH.exists():
            return {}
        raw = STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _write_state_file(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def save_state(user_key: str, state: str) -> None:
    data = _read_state_file()
    chave = _safe_str(user_key) or "default"
    data[chave] = {
        "state": _safe_str(state),
        "created_at": int(time.time()),
    }
    _write_state_file(data)


def load_state(user_key: str) -> Optional[Dict[str, Any]]:
    data = _read_state_file()
    value = data.get(_safe_str(user_key) or "default")
    return value if isinstance(value, dict) else None


def clear_state(user_key: str) -> None:
    try:
        data = _read_state_file()
        chave = _safe_str(user_key) or "default"
        if chave in data:
            data.pop(chave, None)
            _write_state_file(data)
    except Exception:
        pass


def _encode_state_payload(user_key: str, nonce: str) -> str:
    payload = {
        "u": _safe_str(user_key) or "default",
        "n": _safe_str(nonce),
        "t": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_state_payload(state_value: str) -> Dict[str, Any]:
    try:
        texto = _safe_str(state_value)
        if not texto:
            return {}

        padding = "=" * (-len(texto) % 4)
        raw = base64.urlsafe_b64decode((texto + padding).encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))

        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


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
        query_user = st.query_params.get("bi")
        if isinstance(query_user, list):
            query_user = query_user[0] if query_user else ""

        query_user = _safe_str(query_user)
        user_key = _safe_str(user_key)

        self.user_key = query_user or user_key or "default"
        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings.token_store_path)

    def _load_settings(self) -> BlingSettings:
        cfg = st.secrets.get("bling", {})

        return BlingSettings(
            client_id=_safe_str(cfg.get("client_id", "")),
            client_secret=_safe_str(cfg.get("client_secret", "")),
            redirect_uri=_safe_str(cfg.get("redirect_uri", "")),
            authorize_url=_safe_str(
                cfg.get("authorize_url", "https://www.bling.com.br/Api/v3/oauth/authorize")
            ),
            token_url=_safe_str(
                cfg.get("token_url", "https://www.bling.com.br/Api/v3/oauth/token")
            ),
            revoke_url=_safe_str(
                cfg.get("revoke_url", "https://www.bling.com.br/Api/v3/oauth/revoke")
            ),
            api_base_url=_safe_str(
                cfg.get("api_base_url", "https://api.bling.com.br/Api/v3")
            ),
            token_store_path=_safe_str(
                cfg.get("token_store_path", "bling_app_zero/output/bling_tokens.json")
            ),
            stock_write_path=_safe_str(cfg.get("stock_write_path", "/estoques")),
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

    def _redirect_uri_exata(self) -> str:
        # IMPORTANTÍSSIMO:
        # não alterar a redirect_uri cadastrada no Bling.
        # O valor precisa sair exatamente igual ao que está em st.secrets["bling"]["redirect_uri"].
        return _safe_str(self.settings.redirect_uri)

    def build_authorize_url(self, force_reauth: bool = False) -> Optional[str]:
        if not self.is_configured():
            return None

        nonce = secrets.token_hex(24)
        save_state(self.user_key, nonce)

        state_value = _encode_state_payload(self.user_key, nonce)

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self._redirect_uri_exata(),
            "state": state_value,
        }

        if force_reauth:
            params["prompt"] = "consent"

        return f"{self.settings.authorize_url}?{urlencode(params)}"

    def _clear_oauth_query_params(self) -> None:
        try:
            current_params = dict(st.query_params)

            for key in ("code", "state", "error", "error_description"):
                current_params.pop(key, None)

            st.query_params.clear()

            for key, value in current_params.items():
                st.query_params[key] = value
        except Exception:
            pass

    def _resolve_user_key_from_callback_state(self, state_value: str) -> str:
        payload = _decode_state_payload(state_value)
        callback_user_key = _safe_str(payload.get("u"))
        if callback_user_key:
            return callback_user_key
        return self.user_key or "default"

    def _resolve_nonce_from_callback_state(self, state_value: str) -> str:
        payload = _decode_state_payload(state_value)
        return _safe_str(payload.get("n"))

    def handle_oauth_callback(self) -> Dict[str, str]:
        if st.session_state.get("_bling_oauth_processado"):
            return {"status": "idle", "message": ""}

        query_params = st.query_params

        if "code" not in query_params and "error" not in query_params:
            return {"status": "idle", "message": ""}

        st.session_state["_bling_oauth_processado"] = True

        if "error" in query_params:
            msg = str(
                query_params.get(
                    "error_description",
                    query_params.get("error", "Autorização negada."),
                )
            )
            self._clear_oauth_query_params()
            return {"status": "error", "message": f"Falha na autorização do Bling: {msg}"}

        if not self.is_configured():
            self._clear_oauth_query_params()
            return {
                "status": "error",
                "message": "OAuth recebido, mas a configuração do Bling está incompleta.",
            }

        code = _safe_str(query_params.get("code", ""))
        incoming_state = _safe_str(query_params.get("state", ""))

        callback_user_key = self._resolve_user_key_from_callback_state(incoming_state)
        callback_nonce = self._resolve_nonce_from_callback_state(incoming_state)

        self.user_key = callback_user_key or "default"

        saved = load_state(self.user_key)
        if not saved:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State não encontrado."}

        saved_nonce = _safe_str(saved.get("state"))
        created_at = _safe_int(saved.get("created_at"), 0)

        if not callback_nonce or callback_nonce != saved_nonce:
            clear_state(self.user_key)
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido."}

        if int(time.time()) - created_at > STATE_TTL_SECONDS:
            clear_state(self.user_key)
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State expirado."}

        ok, msg = self.exchange_code_for_token(code)

        self._clear_oauth_query_params()
        clear_state(self.user_key)

        if not ok:
            return {"status": "error", "message": msg}

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
            "code": _safe_str(code),
            "redirect_uri": self._redirect_uri_exata(),
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
                return False, f"Erro OAuth: {payload}"

            self.store.save_token_payload(payload, user_key=self.user_key)
            return True, "OK"

        except Exception as exc:
            return False, f"Erro ao autenticar: {exc}"

    def get_connection_status(self) -> Dict[str, Optional[str]]:
        current = self.store.get(self.user_key) or {}
        expires_at = current.get("expires_at")
        now = int(time.time())

        conectado = bool(current.get("access_token")) and (
            not expires_at or now < _safe_int(expires_at, now + 1)
        )

        return {
            "connected": conectado,
            "company_name": current.get("company_name"),
            "last_auth_at": current.get("last_auth_at"),
            "expires_at": expires_at,
        }
