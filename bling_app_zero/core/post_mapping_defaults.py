from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

POST_MAPPING_DEFAULTS: dict[str, str] = {
    'categoria': '',
    'clonar dados do pai': 'Não',
    'condição do produto': 'Novo',
    'condicao do produto': 'Novo',
    'descrição complementar': '',
    'descricao complementar': '',
    'frete grátis': 'Não',
    'frete gratis': 'Não',
    'informações adicionais': '',
    'informacoes adicionais': '',
    'itens p/ caixa': '1',
    'itens por caixa': '1',
    'situação': 'Ativo',
    'situacao': 'Ativo',
    'unidade': 'UN',
    'unidade de medida': 'Centímetro',
    'video': '',
    'vídeo': '',
    'volumes': '1',
}

RULE_KEY_BY_TARGET: dict[str, str] = {
    'unidade': 'measure_unit_default',
    'itens p/ caixa': 'box_items_default',
    'itens por caixa': 'box_items_default',
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


def _default_for_column(column: str, rules: dict[str, Any] | None = None) -> str | None:
    key = normalize_key(column)
    rules = rules if isinstance(rules, dict) else {}

    rule_key = RULE_KEY_BY_TARGET.get(key)
    if rule_key:
        fallback = POST_MAPPING_DEFAULTS.get(key, '')
        return _text(rules.get(rule_key), fallback)

    if key in POST_MAPPING_DEFAULTS:
        return POST_MAPPING_DEFAULTS[key]

    return None


def apply_post_mapping_defaults(df: pd.DataFrame, rules: dict[str, Any] | None = None) -> pd.DataFrame:
    """Aplica padrões finais apenas em células vazias depois do mapeamento manual.

    Regra principal:
    - se a coluna não existir, nada é criado;
    - se o usuário mapeou/preencheu valor, nada é sobrescrito;
    - se a coluna existir e estiver vazia, recebe o padrão final.
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    for column in out.columns:
        default_value = _default_for_column(str(column), rules)
        if default_value is None:
            continue
        out[column] = out[column].apply(lambda value: default_value if _is_empty(value) else clean_cell(value))
    return out


__all__ = ['POST_MAPPING_DEFAULTS', 'apply_post_mapping_defaults']
