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

from bling_app_zero.core.bling_token_store import BlingTokenStore


STATE_PATH = Path("bling_app_zero/output/oauth_state.json")


def _safe_json_load(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# 🔥 LIMPEZA AUTOMÁTICA DE STATES ANTIGOS
def _clean_old_states(data: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    limite = 900  # 15 minutos

    return {
        k: v
        for k, v in data.items()
        if isinstance(v, dict) and (now - int(v.get("created_at", 0))) <= limite
    }


def save_state(user_key: str, state: str) -> None:
    data: Dict[str, Dict[str, Any]] = {}

    try:
        if STATE_PATH.exists():
            raw = STATE_PATH.read_text(encoding="utf-8").strip()
            if raw:
                data = _safe_json_load(raw)
    except Exception:
        data = {}

    data = _clean_old_states(data)

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

        data = _clean_old_states(_safe_json_load(raw))
        return data.get(str(user_key).strip() or "default")
    except Exception:
        return None


def clear_state(user_key: str) -> None:
    try:
        if not STATE_PATH.exists():
            return

        raw = STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return

        data = _safe_json_load(raw)

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

        self.user_key = query_user or user_key or "default"

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

    def _parse_payload(self, resp: httpx.Response) -> Any:
        try:
            if "application/json" in str(resp.headers.get("content-type", "")).lower():
                return resp.json()
        except Exception:
            pass

        return {"raw": resp.text}

    # 🔥 PROTEÇÃO CONTRA EXECUÇÃO DUPLA
    def handle_oauth_callback(self) -> Dict[str, str]:
        if st.session_state.get("_oauth_processado"):
            return {"status": "idle", "message": ""}

        qp = st.query_params

        if "code" not in qp and "error" not in qp:
            return {"status": "idle", "message": ""}

        st.session_state["_oauth_processado"] = True

        if "error" in qp:
            msg = str(qp.get("error_description", qp.get("error", "Autorização negada.")))
            self._clear_oauth_query_params()
            return {"status": "error", "message": f"Falha na autorização do Bling: {msg}"}

        if not self.is_configured():
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Configuração OAuth ausente."}

        code = str(qp.get("code", "")).strip()
        incoming_state = str(qp.get("state", "")).strip()

        if not code:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "Callback sem code."}

        saved = load_state(self.user_key)

        if not saved:
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State não encontrado."}

        if incoming_state != str(saved.get("state", "")):
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State inválido."}

        if (int(time.time()) - int(saved.get("created_at", 0))) > 900:
            clear_state(self.user_key)
            self._clear_oauth_query_params()
            return {"status": "error", "message": "State expirado."}

        ok, msg = self.exchange_code_for_token(code)
        self._clear_oauth_query_params()

        if not ok:
            return {"status": "error", "message": msg}

        clear_state(self.user_key)
        return {"status": "success", "message": "Conta conectada com sucesso."}

    def get_valid_access_token(self) -> Tuple[bool, str]:
        current = self.store.get(self.user_key) or {}

        token = str(current.get("access_token", "")).strip()

        # 🔥 BLINDAGEM
        if not token:
            return False, "Token inválido ou vazio."

        if not self.store.is_expired(current):
            return True, token

        ok, msg = self.refresh_access_token()
        if not ok:
            return False, msg

        refreshed = self.store.get(self.user_key) or {}
        token = str(refreshed.get("access_token", "")).strip()

        return (True, token) if token else (False, "Token inválido após refresh.")
