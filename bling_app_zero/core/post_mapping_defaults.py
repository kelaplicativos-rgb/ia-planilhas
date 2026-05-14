from __future__ import annotations

from typing import Any

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

POST_MAPPING_DEFAULTS_SESSION_KEY = 'bling_post_mapping_defaults'

# BLINGREFORM:
# O preenchimento de campos deixa de ser feito por regras escondidas/defaults.
# Agora a fonte oficial é o mapeamento:
# - escolher coluna
# - escrever valor fixo
# - deixar vazio
DEFAULT_POST_MAPPING_CONFIG: dict[str, Any] = {
    'enabled': False,
}


def get_post_mapping_defaults_config() -> dict[str, Any]:
    config = dict(DEFAULT_POST_MAPPING_CONFIG)
    if st is None:
        return config
    raw = st.session_state.get(POST_MAPPING_DEFAULTS_SESSION_KEY)
    if isinstance(raw, dict):
        config.update(raw)
    config['enabled'] = False
    st.session_state[POST_MAPPING_DEFAULTS_SESSION_KEY] = config
    return config


def apply_post_mapping_defaults(df: pd.DataFrame, rules: dict[str, Any] | None = None) -> pd.DataFrame:
    """Não aplica mais preenchimento automático pós-mapeamento.

    Esta função permanece para compatibilidade do pipeline, mas não altera valores.
    Isso elimina a contradição onde o usuário escolhia "deixar vazio" e um default
    preenchia novamente no CSV final.
    """
    _ = rules
    if df is None:
        return df
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else df


__all__ = [
    'DEFAULT_POST_MAPPING_CONFIG',
    'POST_MAPPING_DEFAULTS_SESSION_KEY',
    'apply_post_mapping_defaults',
    'get_post_mapping_defaults_config',
]
