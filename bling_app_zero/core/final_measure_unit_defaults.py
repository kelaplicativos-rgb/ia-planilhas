from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.dimension_unit_defaults_runtime import DIMENSION_UNIT_DEFAULT, DIMENSION_UNIT_TARGET, normalize_dimension_unit

RESPONSIBLE_FILE = 'bling_app_zero/core/final_measure_unit_defaults.py'

_MEASURE_UNIT_COLUMN_KEYS = {
    'unidade das medidas',
    'unidade de medida',
    'unidade medida',
    'unidade_medida',
    'unidademedida',
    'unidadedasmedidas',
}


@dataclass(frozen=True)
class MeasureUnitResult:
    df: pd.DataFrame
    changed: int = 0
    columns: tuple[str, ...] = ()
    fill_value: str = DIMENSION_UNIT_DEFAULT
    message: str = ''


def _safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value if value is not None else '').strip()


def _norm(value: Any) -> str:
    text = _safe_text(value).lower()
    for old, new in {
        'í': 'i', 'é': 'e', 'ê': 'e', 'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'ô': 'o', 'ó': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c',
    }.items():
        text = text.replace(old, new)
    return ' '.join(text.replace('_', ' ').split())


def looks_like_measure_unit_column(column: object) -> bool:
    key = _norm(column)
    compact = key.replace(' ', '')
    return key in _MEASURE_UNIT_COLUMN_KEYS or compact in _MEASURE_UNIT_COLUMN_KEYS


def _default_from_rules(rules: dict[str, Any] | None) -> str:
    rules = dict(rules or {})
    custom_rules = rules.get('custom_rules')
    if isinstance(custom_rules, list):
        for raw_rule in custom_rules:
            if not isinstance(raw_rule, dict) or not bool(raw_rule.get('enabled', True)):
                continue
            target = _safe_text(raw_rule.get('target_column') or raw_rule.get('condition'))
            if _norm(target) == _norm(DIMENSION_UNIT_TARGET):
                return normalize_dimension_unit(raw_rule.get('fill_value') or rules.get('measure_unit_name_default') or DIMENSION_UNIT_DEFAULT)
    return normalize_dimension_unit(rules.get('measure_unit_name_default') or DIMENSION_UNIT_DEFAULT)


def _normalize_cell(value: Any, fill_value: str) -> str:
    text = _safe_text(value)
    default_value = normalize_dimension_unit(fill_value)
    if not text:
        return '' if default_value == 'VAZIO' else default_value
    normalized = normalize_dimension_unit(text)
    return '' if normalized == 'VAZIO' else normalized


def apply_measure_unit_default_resource(df: pd.DataFrame | None, rules: dict[str, Any] | None = None) -> MeasureUnitResult:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if out.empty:
        return MeasureUnitResult(out, message='Sem dados para Unidade das medidas.')

    columns = [str(column) for column in out.columns if looks_like_measure_unit_column(column)]
    if not columns:
        return MeasureUnitResult(out, message='Modelo final não possui coluna de Unidade das medidas.')

    fill_value = _default_from_rules(rules)
    changed = 0
    for column in columns:
        before = out[column].fillna('').astype(str).tolist()
        out[column] = out[column].map(lambda value: _normalize_cell(value, fill_value))
        after = out[column].fillna('').astype(str).tolist()
        changed += sum(1 for old, new in zip(before, after) if old != new)

    return MeasureUnitResult(
        out.copy().fillna(''),
        changed=changed,
        columns=tuple(columns),
        fill_value=fill_value,
        message=f'Unidade das medidas aplicada em {changed} célula(s).',
    )


__all__ = [
    'MeasureUnitResult',
    'RESPONSIBLE_FILE',
    'apply_measure_unit_default_resource',
    'looks_like_measure_unit_column',
]
