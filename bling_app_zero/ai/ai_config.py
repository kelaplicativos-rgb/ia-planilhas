from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

AI_ENABLED_KEY = 'mapeia_ai_enabled'
AI_USER_API_KEY = 'mapeia_ai_user_openai_api_key'
AI_MODE_KEY = 'mapeia_ai_mode'
AI_MODEL_KEY = 'mapeia_ai_model'
AI_STATUS_KEY = 'mapeia_ai_status'

AI_MODE_SAFE = 'seguro'
AI_MODE_ASSISTED = 'assistido'
AI_MODE_AUTO = 'automatico'
AI_ALLOWED_MODES = (AI_MODE_SAFE, AI_MODE_ASSISTED, AI_MODE_AUTO)
DEFAULT_AI_MODE = AI_MODE_ASSISTED
DEFAULT_AI_MODEL = 'gpt-4o-mini'
SECRET_SECTION_CANDIDATES = ('openai', 'OPENAI', 'ai', 'AI')
SECRET_KEY_CANDIDATES = ('api_key', 'OPENAI_API_KEY', 'openai_api_key')
SECRET_MODEL_CANDIDATES = ('model', 'OPENAI_MODEL', 'openai_model')


@dataclass(frozen=True)
class AISettings:
    enabled: bool
    api_key: str
    mode: str
    model: str
    ready: bool
    status: str


def _clean_api_key(value: object) -> str:
    return str(value or '').strip()


def _secret_get(path: tuple[str, ...]) -> Any:
    current: Any = st.secrets
    try:
        for part in path:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = current[part]
        return current
    except Exception:
        return None


def get_openai_key_from_secrets() -> str:
    """Lê a chave OpenAI do Secrets do app.

    Regra atual do MapeiaAI:
    - a IA não aparece na sidebar;
    - o usuário final não informa chave;
    - o app usa a chave configurada pelo administrador no Streamlit Secrets.
    """
    for section in SECRET_SECTION_CANDIDATES:
        for key in SECRET_KEY_CANDIDATES:
            value = _secret_get((section, key))
            cleaned = _clean_api_key(value)
            if cleaned:
                return cleaned
    for key in SECRET_KEY_CANDIDATES:
        value = _secret_get((key,))
        cleaned = _clean_api_key(value)
        if cleaned:
            return cleaned
    return ''


def get_user_openai_key() -> str:
    """Compatibilidade: retorna a chave do Secrets, não da sessão do usuário."""
    return get_openai_key_from_secrets()


def get_ai_mode() -> str:
    mode = str(st.session_state.get(AI_MODE_KEY) or DEFAULT_AI_MODE).strip().lower()
    return mode if mode in AI_ALLOWED_MODES else DEFAULT_AI_MODE


def get_ai_model() -> str:
    for section in SECRET_SECTION_CANDIDATES:
        for key in SECRET_MODEL_CANDIDATES:
            value = _secret_get((section, key))
            model = str(value or '').strip()
            if model:
                return model
    for key in SECRET_MODEL_CANDIDATES:
        value = _secret_get((key,))
        model = str(value or '').strip()
        if model:
            return model
    model = str(st.session_state.get(AI_MODEL_KEY) or DEFAULT_AI_MODEL).strip()
    return model or DEFAULT_AI_MODEL


def ai_is_enabled() -> bool:
    return bool(get_openai_key_from_secrets())


def get_ai_settings() -> AISettings:
    api_key = get_openai_key_from_secrets()
    enabled = bool(api_key)
    ready = enabled and bool(api_key)
    status = 'IA pronta via Secrets' if ready else 'Configure a chave OpenAI no Secrets para ativar a IA.'
    st.session_state[AI_STATUS_KEY] = status
    return AISettings(
        enabled=enabled,
        api_key=api_key,
        mode=get_ai_mode(),
        model=get_ai_model(),
        ready=ready,
        status=status,
    )


def clear_ai_key() -> None:
    """Não remove Secrets. Apenas limpa estados legados de sessão."""
    st.session_state.pop(AI_USER_API_KEY, None)
    st.session_state.pop(AI_ENABLED_KEY, None)
    st.session_state[AI_STATUS_KEY] = 'IA controlada pelo Secrets'


__all__ = [
    'AISettings',
    'AI_ALLOWED_MODES',
    'AI_ENABLED_KEY',
    'AI_MODE_ASSISTED',
    'AI_MODE_AUTO',
    'AI_MODE_KEY',
    'AI_MODE_SAFE',
    'AI_MODEL_KEY',
    'AI_STATUS_KEY',
    'AI_USER_API_KEY',
    'DEFAULT_AI_MODEL',
    'DEFAULT_AI_MODE',
    'ai_is_enabled',
    'clear_ai_key',
    'get_ai_mode',
    'get_ai_model',
    'get_ai_settings',
    'get_openai_key_from_secrets',
    'get_user_openai_key',
]