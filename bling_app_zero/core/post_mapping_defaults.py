from __future__ import annotations

import importlib
from collections.abc import MutableMapping
from typing import Any

import pandas as pd

POST_MAPPING_DEFAULTS_SESSION_KEY = 'bling_post_mapping_defaults'
_FALLBACK_STATE: dict[str, Any] = {}

# Compatibilidade com telas antigas de mapeamento/sidebar.
# BLINGREFORM: os defaults pós-mapeamento foram desplugados do download final,
# então este dicionário permanece vazio para não pintar campos nem preencher valores
# de forma escondida.
COLUMN_DEFAULT_KEY_BY_TARGET: dict[str, str] = {}

# BLINGREFORM:
# O preenchimento de campos deixa de ser feito por regras escondidas/defaults.
# Agora a fonte oficial é o mapeamento:
# - escolher coluna
# - escrever valor fixo
# - deixar vazio
DEFAULT_POST_MAPPING_CONFIG: dict[str, Any] = {
    'enabled': False,
}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def get_post_mapping_defaults_config(state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    config = dict(DEFAULT_POST_MAPPING_CONFIG)
    store = state_store(state)
    raw = store.get(POST_MAPPING_DEFAULTS_SESSION_KEY)
    if isinstance(raw, dict):
        config.update(raw)
    config['enabled'] = False
    store[POST_MAPPING_DEFAULTS_SESSION_KEY] = config
    return config


def apply_post_mapping_defaults(df: pd.DataFrame, rules: dict[str, Any] | None = None) -> pd.DataFrame:
    """Não aplica mais preenchimento automático pós-mapeamento.

    Esta função permanece para compatibilidade do pipeline e de imports antigos,
    mas não altera valores. Isso elimina a contradição onde o usuário escolhia
    "deixar vazio" e um default preenchia novamente no CSV final.
    """
    _ = rules
    if df is None:
        return df
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else df


__all__ = [
    'COLUMN_DEFAULT_KEY_BY_TARGET',
    'DEFAULT_POST_MAPPING_CONFIG',
    'POST_MAPPING_DEFAULTS_SESSION_KEY',
    'apply_post_mapping_defaults',
    'get_post_mapping_defaults_config',
    'state_store',
]
