from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/critical_empty_fields_guard.py'

# Campos sensíveis que exigem escolha consciente do usuário.
# Eles NÃO são forçados a vazio. Apenas não devem ser preenchidos por automação
# silenciosa/auto-green. Se o usuário selecionar uma coluna ou valor fixo, o
# sistema deve respeitar e exportar o dado.
MANUAL_CHOICE_COMPACT_KEYS = {
    'tag',
    'tags',
    'etiqueta',
    'etiquetas',
    'grupodetags',
    'grupotags',
    'tagsdoproduto',
    'tagdoproduto',
    'codigopai',
    'codpai',
    'skupai',
    'idpai',
}


def _compact(value: object) -> str:
    return normalize_key(value).replace(' ', '')


def is_manual_choice_target(column: object) -> bool:
    key = _compact(column)
    if key in MANUAL_CHOICE_COMPACT_KEYS:
        return True
    return key.startswith('codigopai') or key.startswith('grupodetags') or key.startswith('tagsdoproduto')


# Compatibilidade com patches antigos: o nome antigo continua existindo, mas
# agora significa apenas "campo sensível que requer escolha manual".
def is_critical_empty_target(column: object) -> bool:
    return is_manual_choice_target(column)


# Compatibilidade: não remove mais nada. Deixar vazio ou preencher é decisão do usuário.
def strip_critical_empty_mappings(mapping: Mapping[str, str] | None) -> tuple[dict[str, str], list[dict[str, str]]]:
    return {str(key): str(value or '').strip() for key, value in dict(mapping or {}).items()}, []


# Compatibilidade: não limpa mais o download final. Se o usuário mapeou, exporta.
def force_critical_empty_columns(df: pd.DataFrame | None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(), []


__all__ = [
    'is_manual_choice_target',
    'is_critical_empty_target',
    'strip_critical_empty_mappings',
    'force_critical_empty_columns',
]
