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

# 🔥 CORREÇÃO DE IMPORT
try:
    from bling_app_zero.services.bling.bling_token_store import BlingTokenStore
except ImportError:
    from bling_app_zero.core.bling_token_store import BlingTokenStore


STATE_PATH = Path("bling_app_zero/output/oauth_state.json")


def save_state(user_key: str, state: str) -> None:
    data: Dict[str, Dict[str, Any]] = {}

    try:
        if STATE_PATH.exists():
            raw = STATE_PATH.read_text(encoding="utf-8").strip()
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    data = loaded
    except Exception:
        data = {}

    data[str(user_key).strip() or "default"] = {
        "state": str(state).strip(),
        "created_at": int(time.time()),
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_state(user_key: str) -> Optional[Dict[str, Any]]:
    try:
        if not STATE_PATH.exists():
            return None

        raw = STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return None

        data = json.loads(raw)
        if not isinstance(data, dict):
            return None

        value = data.get(str(user_key).strip() or "default")
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def clear_state(user_key: str) -> None:
    try:
        if not STATE_PATH.exists():
            return

        raw = STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return

        data = json.loads(raw)
        if not isinstance(data, dict):
            return

        chave = str(user_key).strip() or "default"
        if chave in data:
            data.pop(chave, None)
            STATE_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass


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

        query_user = str(query_user or "").strip()
        user_key = str(user_key or "").strip()

        if query_user:
            self.user_key = query_user
        else:
            self.user_key = user_key or "default"

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
        save_state(self.user_key, state)

        redirect_uri = self.settings.redirect_uri
        separador = "&" if "?" in redirect_uri else "?"
        redirect_uri_com_user = f"{redirect_uri}{separador}bi={self.user_key}"

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri_com_user,
            "state": state,
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
            return {"status": "error", "message": f"Falha na autorização do Bling: {msg}"}

        if not self.is_configured():
            self._clear_oauth_query_params()
            return {
                "status": "error",
                "message": "OAuth recebido, mas a configuração fixa do app ainda não está preenchida.",
            }

        code = str(query_params.get("code", "")).strip()
        incoming_state = str(query_params.get("state", "")).strip()

        if not code:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Callback sem authorization code."}

        saved = load_state(self.user_key)

        if not saved:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State não encontrado. Gere nova conexão."}

        expected_state = str(saved.get("state", "")).strip()
        created_at = int(saved.get("created_at", 0) or 0)

        if not expected_state or incoming_state != expected_state:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido na autenticação com o Bling."}

        if created_at and (int(time.time()) - created_at) > 15 * 60:
            clear_state(self.user_key)
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State expirado. Gere nova autenticação."}

        ok, msg = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()

        if not ok:
            return {"status": "error", "message": msg}

        clear_state(self.user_key)
        return {"status": "success", "message": "Conta Bling conectada com sucesso."}

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        redirect_uri = self.settings.redirect_uri
        separador = "&" if "?" in redirect_uri else "?"
        redirect_uri_com_user = f"{redirect_uri}{separador}bi={self.user_key}"

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "enable-jwt": "1",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri_com_user,
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
                return False, f"Erro ao trocar code por token: HTTP {resp.status_code} | {payload}"

            self.store.save_token_payload(payload, user_key=self.user_key)
            self._hydrate_company_name_from_jwt()
            return True, "OK"
        except Exception as exc:
            return False, f"Erro ao autenticar com o Bling: {exc}"

    def get_connection_status(self) -> Dict[str, Optional[str]]:
        current = self.store.get(self.user_key) or {}
        connected = bool(current.get("access_token"))

        return {
            "connected": connected,
            "company_name": current.get("company_name"),
            "last_auth_at": current.get("last_auth_at"),
            "expires_at": current.get("expires_at"),
        }
