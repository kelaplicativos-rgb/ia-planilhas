from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

POST_MAPPING_DEFAULTS_SESSION_KEY = 'bling_post_mapping_defaults'

DEFAULT_POST_MAPPING_CONFIG: dict[str, Any] = {
    'enabled': True,
    'category_default': '',
    'clone_parent_default': 'Não',
    'product_condition_default': 'Novo',
    'short_description_from_complement': True,
    'description_complement_default': '',
    'free_shipping_default': 'Não',
    'additional_info_default': '',
    'box_items_default': '1',
    'situation_default': 'Ativo',
    'unit_default': 'UN',
    'measure_unit_name_default': 'Centímetro',
    'video_default': '',
    'volumes_default': '1',
}

COLUMN_DEFAULT_KEY_BY_TARGET: dict[str, str] = {
    'categoria': 'category_default',
    'clonar dados do pai': 'clone_parent_default',
    'condição do produto': 'product_condition_default',
    'condicao do produto': 'product_condition_default',
    'descrição complementar': 'description_complement_default',
    'descricao complementar': 'description_complement_default',
    'frete grátis': 'free_shipping_default',
    'frete gratis': 'free_shipping_default',
    'informações adicionais': 'additional_info_default',
    'informacoes adicionais': 'additional_info_default',
    'itens p/ caixa': 'box_items_default',
    'itens por caixa': 'box_items_default',
    'situação': 'situation_default',
    'situacao': 'situation_default',
    'unidade': 'unit_default',
    'unidade de medida': 'measure_unit_name_default',
    'video': 'video_default',
    'vídeo': 'video_default',
    'volumes': 'volumes_default',
}

SHORT_DESCRIPTION_TARGETS = {
    'descrição curta',
    'descricao curta',
    'descrição curta do produto',
    'descricao curta do produto',
}

DESCRIPTION_COMPLEMENT_TARGETS = {
    'descrição complementar',
    'descricao complementar',
}


def _text(value: Any, fallback: str = '') -> str:
    text = clean_cell(value).strip()
    return text if text else fallback


def _is_empty(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    return normalize_key(text) in {
        'nan',
        'none',
        'null',
        'na',
        'n/a',
        'nao informado',
        'naoinformado',
        'sem informacao',
        'seminformacao',
    }


def _sidebar_config() -> dict[str, Any]:
    """Lê somente a configuração já inicializada pelo sidebar.

    Se o painel do sidebar ainda não gravou a configuração na sessão, o core não
    aplica padrões por conta própria. Isso evita regra oculta/fantasma.
    """
    if st is None:
        config = dict(DEFAULT_POST_MAPPING_CONFIG)
        config['enabled'] = False
        return config

    raw = st.session_state.get(POST_MAPPING_DEFAULTS_SESSION_KEY)
    if not isinstance(raw, dict):
        config = dict(DEFAULT_POST_MAPPING_CONFIG)
        config['enabled'] = False
        return config

    config = dict(DEFAULT_POST_MAPPING_CONFIG)
    for key in config:
        if key in raw:
            config[key] = raw[key]
    config['enabled'] = bool(config.get('enabled', True))
    config['short_description_from_complement'] = bool(config.get('short_description_from_complement', True))
    return config


def _default_for_column(column: str, config: dict[str, Any]) -> str | None:
    key = normalize_key(column)
    config_key = COLUMN_DEFAULT_KEY_BY_TARGET.get(key)
    if not config_key:
        return None
    return _text(config.get(config_key), str(DEFAULT_POST_MAPPING_CONFIG.get(config_key, '')))


def _find_column(df: pd.DataFrame, normalized_names: set[str]) -> str:
    for column in df.columns:
        if normalize_key(column) in normalized_names:
            return str(column)
    return ''


def _apply_short_description_link(out: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if not bool(config.get('short_description_from_complement', True)):
        return out
    short_column = _find_column(out, SHORT_DESCRIPTION_TARGETS)
    complement_column = _find_column(out, DESCRIPTION_COMPLEMENT_TARGETS)
    if not short_column or not complement_column:
        return out
    out[short_column] = [
        clean_cell(complement) if _is_empty(short) and not _is_empty(complement) else clean_cell(short)
        for short, complement in zip(out[short_column], out[complement_column])
    ]
    return out


def apply_post_mapping_defaults(df: pd.DataFrame, rules: dict[str, Any] | None = None) -> pd.DataFrame:
    """Aplica somente padrões visíveis no sidebar após o mapeamento manual.

    Regra principal:
    - se o painel do sidebar ainda não inicializou essa regra, nada é aplicado;
    - se o usuário desligar no sidebar, nada é aplicado;
    - se a coluna não existir, nada é criado;
    - se o usuário mapeou/preencheu valor, nada é sobrescrito;
    - se a coluna existir e estiver vazia, recebe o padrão configurado no sidebar.
    """
    if df is None or df.empty:
        return df

    config = _sidebar_config()
    if not bool(config.get('enabled', True)):
        return df

    out = df.copy()
    for column in out.columns:
        default_value = _default_for_column(str(column), config)
        if default_value is None:
            continue
        out[column] = out[column].apply(lambda value: default_value if _is_empty(value) else clean_cell(value))

    out = _apply_short_description_link(out, config)
    return out


__all__ = [
    'DEFAULT_POST_MAPPING_CONFIG',
    'POST_MAPPING_DEFAULTS_SESSION_KEY',
    'apply_post_mapping_defaults',
]
