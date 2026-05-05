from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd
import streamlit as st


VAULT_PREFIX = "__bling_vault__"


@st.cache_resource(show_spinner=False)
def _global_vault() -> dict[str, Any]:
    """Cofre em memória do processo Streamlit.

    O st.session_state protege contra rerun comum. Este cofre global ajuda também
    quando a tela reconecta/atualiza dentro do mesmo processo do Streamlit Cloud.
    Em reinício completo do servidor, o usuário ainda precisará reenviar arquivos.
    """
    return {}


def _vault_key(key: str) -> str:
    return f"{VAULT_PREFIX}:{str(key)}"


def df_valido(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    base.columns = [str(c).replace("\ufeff", "").strip() for c in base.columns]
    base = base.loc[:, [str(c).strip() != "" for c in base.columns]]
    return base.dropna(how="all").fillna("")


def guardar_df(key: str, df: pd.DataFrame) -> pd.DataFrame:
    base = normalizar_df(df)
    if not df_valido(base):
        return base

    st.session_state[key] = base.copy()
    st.session_state[_vault_key(key)] = base.copy()
    _global_vault()[key] = base.copy()
    return base


def restaurar_df(key: str) -> pd.DataFrame | None:
    atual = st.session_state.get(key)
    if df_valido(atual):
        guardar_df(key, atual.copy())
        return atual.copy()

    local = st.session_state.get(_vault_key(key))
    if df_valido(local):
        base = local.copy()
        st.session_state[key] = base.copy()
        _global_vault()[key] = base.copy()
        return base

    global_df = _global_vault().get(key)
    if df_valido(global_df):
        base = global_df.copy()
        st.session_state[key] = base.copy()
        st.session_state[_vault_key(key)] = base.copy()
        return base

    return None


def guardar_valor(key: str, value: Any) -> None:
    try:
        safe_value = deepcopy(value)
    except Exception:
        safe_value = value
    st.session_state[key] = safe_value
    st.session_state[_vault_key(key)] = safe_value
    _global_vault()[key] = safe_value


def restaurar_valor(key: str, default: Any = None) -> Any:
    if key in st.session_state and st.session_state.get(key) not in (None, ""):
        guardar_valor(key, st.session_state.get(key))
        return st.session_state.get(key)

    if _vault_key(key) in st.session_state:
        value = st.session_state.get(_vault_key(key))
        st.session_state[key] = value
        _global_vault()[key] = value
        return value

    if key in _global_vault():
        value = _global_vault().get(key)
        st.session_state[key] = value
        st.session_state[_vault_key(key)] = value
        return value

    return default


def restaurar_chaves_df(keys: list[str]) -> None:
    for key in keys:
        restaurar_df(key)


def limpar_vault(prefixes: tuple[str, ...] = ("stable_", "supplier_")) -> None:
    vault = _global_vault()
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefixes) or str(key).startswith(VAULT_PREFIX):
            st.session_state.pop(key, None)
    for key in list(vault.keys()):
        if str(key).startswith(prefixes):
            vault.pop(key, None)
