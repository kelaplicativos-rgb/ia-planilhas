
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import streamlit as st


# ============================================================
# CONFIG
# ============================================================

SESSION_FILE = Path("bling_app_zero/output/user_session.json")


# ============================================================
# HELPERS
# ============================================================

def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalizar(valor: Any) -> str:
    if valor is None:
        return ""
    txt = str(valor).strip()
    if txt.lower() in {"nan", "none", "null"}:
        return ""
    return txt


def _safe_load() -> dict:
    if not SESSION_FILE.exists():
        return {}
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_save(data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================
# USER KEY
# ============================================================

def get_user_key() -> str:
    """
    Identificador único do usuário/sessão.

    Prioridade:
    1. query param ?bi=
    2. session_state
    3. cria novo
    """
    try:
        bi = _normalizar(st.query_params.get("bi", ""))
        if bi:
            st.session_state["user_key"] = bi
            return bi
    except Exception:
        pass

    key = _normalizar(st.session_state.get("user_key", ""))
    if key:
        return key

    novo = f"user_{_now_iso()}"
    st.session_state["user_key"] = novo
    return novo


# ============================================================
# SESSÃO DE TOKENS
# ============================================================

def salvar_tokens(tokens: dict) -> None:
    data = _safe_load()
    user = get_user_key()

    data[user] = {
        "tokens": tokens,
        "updated_at": _now_iso(),
    }

    _safe_save(data)


def obter_tokens() -> dict:
    data = _safe_load()
    user = get_user_key()
    return data.get(user, {}).get("tokens", {}) or {}


def limpar_tokens() -> None:
    data = _safe_load()
    user = get_user_key()

    if user in data:
        del data[user]

    _safe_save(data)


# ============================================================
# TOKEN HELPERS
# ============================================================

def get_access_token() -> str:
    tokens = obter_tokens()
    return _normalizar(tokens.get("access_token"))


def get_refresh_token() -> str:
    tokens = obter_tokens()
    return _normalizar(tokens.get("refresh_token"))


def salvar_token_bundle(bundle: dict) -> None:
    """
    Salva bundle padrão vindo do bling_auth
    """
    salvar_tokens(bundle)


# ============================================================
# EXPIRAÇÃO
# ============================================================

def token_expirado() -> bool:
    tokens = obter_tokens()
    expires_at = _normalizar(tokens.get("expires_at"))

    if not expires_at:
        return True

    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= dt
    except Exception:
        return True


# ============================================================
# STATUS
# ============================================================

def usuario_conectado() -> bool:
    return bool(get_access_token())


def resumo_sessao() -> dict:
    tokens = obter_tokens()

    return {
        "conectado": usuario_conectado(),
        "access_token": bool(tokens.get("access_token")),
        "refresh_token": bool(tokens.get("refresh_token")),
        "expirado": token_expirado(),
        "updated_at": tokens.get("updated_at", ""),
    }
