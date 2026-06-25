from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/critical_empty_fields_guard.py'

# Campos que não devem ser preenchidos automaticamente no fluxo Universal.
# Tags inválidas e Código Pai indevido são causas comuns de falha/variação errada no Bling.
CRITICAL_EMPTY_COMPACT_KEYS = {
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


def is_critical_empty_target(column: object) -> bool:
    key = _compact(column)
    if key in CRITICAL_EMPTY_COMPACT_KEYS:
        return True
    return key.startswith('codigopai') or key.startswith('grupodetags') or key.startswith('tagsdoproduto')


def strip_critical_empty_mappings(mapping: Mapping[str, str] | None) -> tuple[dict[str, str], list[dict[str, str]]]:
    result = {str(key): str(value or '').strip() for key, value in dict(mapping or {}).items()}
    report: list[dict[str, str]] = []
    for target, source in list(result.items()):
        if is_critical_empty_target(target) and source:
            result[target] = ''
            report.append({
                'target': target,
                'blocked_source': source,
                'reason': 'campo crítico deve ficar vazio no fluxo Universal: Tags/Código Pai não podem ser auto preenchidos por farol ou coluna igual',
                'responsible_file': RESPONSIBLE_FILE,
            })
    return result, report


def force_critical_empty_columns(df: pd.DataFrame | None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(), []
    out = df.copy().fillna('')
    report: list[dict[str, Any]] = []
    for column in list(out.columns):
        if not is_critical_empty_target(column):
            continue
        series = out[column].fillna('').astype(str).str.strip()
        filled = int(series.ne('').sum())
        if filled:
            out[column] = ''
            report.append({
                'column': str(column),
                'cleared_cells': filled,
                'reason': 'campo crítico limpo antes do download/API final',
                'responsible_file': RESPONSIBLE_FILE,
            })
    return out, report


__all__ = ['is_critical_empty_target', 'strip_critical_empty_mappings', 'force_critical_empty_columns']
