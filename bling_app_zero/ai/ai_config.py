from __future__ import annotations

from dataclasses import dataclass

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


def get_user_openai_key() -> str:
    """Retorna somente a chave digitada pelo usuário na sessão atual.

    Regra BYOK do Mapeia.AI: não buscar chave em st.secrets, arquivo .env,
    variável de ambiente ou fallback administrativo. Cada usuário informa a
    própria chave na sidebar para ativar a IA naquela sessão.
    """
    return _clean_api_key(st.session_state.get(AI_USER_API_KEY))


def get_ai_mode() -> str:
    mode = str(st.session_state.get(AI_MODE_KEY) or DEFAULT_AI_MODE).strip().lower()
    return mode if mode in AI_ALLOWED_MODES else DEFAULT_AI_MODE


def get_ai_model() -> str:
    model = str(st.session_state.get(AI_MODEL_KEY) or DEFAULT_AI_MODEL).strip()
    return model or DEFAULT_AI_MODEL


def ai_is_enabled() -> bool:
    return bool(st.session_state.get(AI_ENABLED_KEY)) and bool(get_user_openai_key())


def get_ai_settings() -> AISettings:
    api_key = get_user_openai_key()
    enabled = bool(st.session_state.get(AI_ENABLED_KEY))
    ready = enabled and bool(api_key)
    status = 'IA pronta' if ready else ('Informe sua chave OpenAI para ativar a IA.' if enabled else 'IA desativada')
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
    st.session_state.pop(AI_USER_API_KEY, None)
    st.session_state[AI_ENABLED_KEY] = False
    st.session_state[AI_STATUS_KEY] = 'IA desativada'


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
    'get_user_openai_key',
]
