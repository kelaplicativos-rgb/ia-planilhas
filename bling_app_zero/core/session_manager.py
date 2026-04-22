
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from datetime import datetime


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path("bling_app_zero/output")
BASE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = BASE_DIR / "site_session.json"


# ============================================================
# DETECÇÃO LOGIN / CAPTCHA
# ============================================================

def detectar_login_captcha(html: str) -> Dict[str, Any]:
    html_lower = (html or "").lower()

    login_detectado = any(
        termo in html_lower
        for termo in ["login", "senha", "password", "entrar"]
    )

    captcha_detectado = any(
        termo in html_lower
        for termo in ["captcha", "recaptcha", "g-recaptcha"]
    )

    return {
        "login_detectado": login_detectado,
        "captcha_detectado": captcha_detectado,
        "status": "login_captcha_detectado" if captcha_detectado else "login_detectado" if login_detectado else "livre",
        "mensagem": "Captcha detectado. Login assistido necessário." if captcha_detectado else "",
    }


# ============================================================
# STORAGE / SESSION
# ============================================================

def salvar_storage_state(data: Dict[str, Any]) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "data": data or {},
    }

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def carregar_storage_state() -> Dict[str, Any]:
    if not SESSION_FILE.exists():
        return {}

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
            return payload.get("data", {})
    except Exception:
        return {}


# ============================================================
# AUTH CONTEXT
# ============================================================

def montar_auth_context(storage_state: Dict[str, Any]) -> Dict[str, Any]:
    if not storage_state:
        return {}

    return {
        "cookies": storage_state.get("cookies", []),
        "headers": storage_state.get("headers", {}),
        "storage_state": storage_state,
    }


# ============================================================
# STATUS DA SESSÃO
# ============================================================

def sessao_esta_pronta() -> bool:
    state = carregar_storage_state()
    return bool(state and state.get("cookies"))


def limpar_sessao() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


# ============================================================
# LOGIN ASSISTIDO (PLACEHOLDER CONTROLADO)
# ============================================================

def iniciar_login_assistido(url_login: str) -> Dict[str, Any]:
    """
    Aqui é onde o Playwright deve ser integrado futuramente.
    Por enquanto:
    - abre fluxo manual
    - usuário loga
    - depois salvamos cookies manualmente
    """

    return {
        "status": "aguardando_login_manual",
        "url": url_login,
        "mensagem": "Abra o navegador, faça login e depois capture a sessão.",
    }


def finalizar_login_assistido(cookies: list, headers: dict | None = None) -> None:
    """
    Recebe cookies capturados (via Playwright ou manual)
    e salva sessão reutilizável
    """

    storage = {
        "cookies": cookies,
        "headers": headers or {},
    }

    salvar_storage_state(storage)


# ============================================================
# DEBUG
# ============================================================

def get_session_debug() -> Dict[str, Any]:
    state = carregar_storage_state()

    return {
        "existe_sessao": bool(state),
        "cookies": len(state.get("cookies", [])) if state else 0,
        "timestamp": state.get("timestamp") if isinstance(state, dict) else None,
    }
