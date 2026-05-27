from __future__ import annotations

import streamlit as st

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FINISH_MODE_KEY = 'bling_finish_mode'
FINISH_MODE_API = 'api_direct'
FINISH_MODE_CSV = 'csv_download'
SKIP_DIRECT_BLING_KEY = 'skip_direct_bling_connection_this_flow'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'

# bling_csv permanece somente como valor legado para não quebrar imports antigos.
# Em tempo de execução, qualquer tentativa de usar bling_csv vira universal.
VALID_CONTEXTS = {CONTEXT_BLING_API, CONTEXT_UNIVERSAL}
LEGACY_CONTEXT_REDIRECTS = {
    'bling': CONTEXT_BLING_API,
    CONTEXT_BLING_CSV: CONTEXT_UNIVERSAL,
}


def normalize_entry_context(context: object, default: str = CONTEXT_BLING_API) -> str:
    value = str(context or '').strip().lower()
    if value in LEGACY_CONTEXT_REDIRECTS:
        return LEGACY_CONTEXT_REDIRECTS[value]
    if value in VALID_CONTEXTS:
        return value
    return default


def entry_context(default: str = CONTEXT_BLING_API) -> str:
    normalized_default = normalize_entry_context(default, CONTEXT_UNIVERSAL)
    current = st.session_state.get(HOME_ENTRY_CONTEXT_KEY)
    normalized = normalize_entry_context(current, normalized_default)
    if current and current != normalized:
        st.session_state[HOME_ENTRY_CONTEXT_KEY] = normalized
    return normalized


def set_entry_context(context: str) -> None:
    st.session_state[HOME_ENTRY_CONTEXT_KEY] = normalize_entry_context(context, CONTEXT_UNIVERSAL)


def finish_mode() -> str:
    return str(st.session_state.get(FINISH_MODE_KEY) or '').strip()


def set_finish_mode(mode: str) -> None:
    st.session_state[FINISH_MODE_KEY] = str(mode or '').strip()


def clear_finish_mode() -> None:
    st.session_state.pop(FINISH_MODE_KEY, None)


def is_bling_api_context() -> bool:
    return entry_context() == CONTEXT_BLING_API


def is_bling_csv_context() -> bool:
    # Legado desativado: bling_csv é tratado como universal.
    return False


def is_universal_context() -> bool:
    return entry_context(default=CONTEXT_UNIVERSAL) == CONTEXT_UNIVERSAL


def is_api_direct_mode() -> bool:
    return is_bling_api_context() and finish_mode() == FINISH_MODE_API


def activate_csv_finish_mode() -> None:
    set_finish_mode(FINISH_MODE_CSV)
    st.session_state[SKIP_DIRECT_BLING_KEY] = True


def activate_api_finish_mode() -> None:
    set_finish_mode(FINISH_MODE_API)
    st.session_state.pop(SKIP_DIRECT_BLING_KEY, None)


def clear_api_skip_flag() -> None:
    st.session_state.pop(SKIP_DIRECT_BLING_KEY, None)


__all__ = [
    'CONTEXT_BLING_API',
    'CONTEXT_BLING_CSV',
    'CONTEXT_UNIVERSAL',
    'FINISH_MODE_API',
    'FINISH_MODE_CSV',
    'FINISH_MODE_KEY',
    'HOME_ENTRY_CONTEXT_KEY',
    'SKIP_DIRECT_BLING_KEY',
    'activate_api_finish_mode',
    'activate_csv_finish_mode',
    'clear_api_skip_flag',
    'clear_finish_mode',
    'entry_context',
    'finish_mode',
    'is_api_direct_mode',
    'is_bling_api_context',
    'is_bling_csv_context',
    'is_universal_context',
    'normalize_entry_context',
    'set_entry_context',
    'set_finish_mode',
]
