# 🔥 VERSÃO CORRIGIDA - STATE PERSISTENTE (NÃO QUEBRA COM STREAMLIT)

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
from pathlib import Path

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore


STATE_PATH = Path("bling_app_zero/output/oauth_state.json")


def save_state(user_key: str, state: str):
    data = {}
    if STATE_PATH.exists():
        data = json.loads(STATE_PATH.read_text())

    data[user_key] = {
        "state": state,
        "created_at": int(time.time())
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data))


def load_state(user_key: str):
    if not STATE_PATH.exists():
        return None

    data = json.loads(STATE_PATH.read_text())
    return data.get(user_key)


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
        self.user_key = str(user_key or "default").strip() or "default"
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

        # 🔥 SALVA EM ARQUIVO (NÃO SESSION)
        save_state(self.user_key, state)

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
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

        code = str(query_params.get("code", "")).strip()
        incoming_state = str(query_params.get("state", "")).strip()

        # 🔥 CARREGA DO ARQUIVO
        saved = load_state(self.user_key)

        if not saved:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State não encontrado. Gere nova conexão."}

        if incoming_state != saved.get("state"):
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido na autenticação com o Bling."}

        if int(time.time()) - saved.get("created_at", 0) > 15 * 60:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State expirado. Gere nova autenticação."}

        ok, msg = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()

        if not ok:
            return {"status": "error", "message": msg}

        return {"status": "success", "message": "Conta Bling conectada com sucesso."}

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(self.settings.token_url, headers=headers, data=data)

            payload = resp.json()

            if resp.status_code >= 400:
                return False, f"Erro ao trocar code por token: {payload}"

            self.store.save_token_payload(payload, user_key=self.user_key)
            return True, "OK"

        except Exception as exc:
            return False, str(exc)
