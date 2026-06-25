from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from bling_app_zero.core.category_intelligence import (
    REVIEW_CATEGORY,
    canonicalize_category,
    looks_like_product_title,
    normalize_text,
)
from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.text import normalize_key as normalize_column_key

RESPONSIBLE_FILE = 'bling_app_zero/core/category_mapping_guard.py'

CATEGORY_SOURCE_PRIORITY = (
    'Categoria do produto',
    'Categoria',
    'categoria_sugerida_ia',
    'categoria_atual_ia',
    'category',
    'breadcrumb',
    'departamento',
    'grupo',
    'familia',
    'família',
)

CATEGORY_TARGET_TERMS = ('categoria', 'category', 'departamento', 'grupo', 'familia', 'família')


def _frame_columns(frame: Any) -> list[str]:
    columns = getattr(frame, 'columns', None)
    if columns is None:
        return []
    try:
        return [str(column) for column in list(columns)]
    except Exception:
        return []


def _target_is_category(target: object) -> bool:
    target_text = str(target or '').strip()
    target_key = normalize_column_key(target_text)
    if infer_kind(target_text) == 'categoria':
        return True
    return any(normalize_column_key(term) in target_key for term in CATEGORY_TARGET_TERMS)


def _source_name_priority(source: str, target_columns: Sequence[str] = ()) -> int:
    source_key = normalize_column_key(source)
    compact_source = source_key.replace(' ', '')
    for target in target_columns:
        if _target_is_category(target) and normalize_column_key(target).replace(' ', '') == compact_source:
            return 0
    for index, candidate in enumerate(CATEGORY_SOURCE_PRIORITY, start=1):
        candidate_key = normalize_column_key(candidate)
        if source_key == candidate_key:
            return index
        if candidate_key and (candidate_key in source_key or source_key in candidate_key):
            return index + 10
    if any(normalize_column_key(term) in source_key for term in CATEGORY_TARGET_TERMS):
        return 40
    return 100


def _values(df: pd.DataFrame, column: str, limit: int = 120) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    try:
        series = df[column].fillna('').astype(str)
    except Exception:
        return values
    for value in series.head(limit * 2):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null'}:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def _is_safe_category_value(value: object) -> tuple[bool, str]:
    text = str(value or '').strip()
    if not text:
        return False, 'vazio'
    if text == REVIEW_CATEGORY:
        return False, 'revisar manualmente'
    canonical, _changed, reason = canonicalize_category(text)
    if canonical and canonical != REVIEW_CATEGORY:
        return True, reason
    if looks_like_product_title(text):
        return False, 'bloqueado: valor parece título de produto'
    return False, reason or 'fora do catálogo seguro'


def category_source_quality(df: pd.DataFrame, column: str) -> dict[str, object]:
    values = _values(df, column)
    total = len(values)
    if not values:
        return {
            'safe': False,
            'total': 0,
            'safe_ratio': 0.0,
            'title_ratio': 0.0,
            'reason': 'coluna sem valores de categoria',
        }

    safe_count = 0
    title_count = 0
    invalid_examples: list[str] = []
    for value in values:
        safe, reason = _is_safe_category_value(value)
        if safe:
            safe_count += 1
        else:
            if looks_like_product_title(value):
                title_count += 1
            if len(invalid_examples) < 3:
                invalid_examples.append(f'{str(value)[:70]} ({reason})')

    safe_ratio = safe_count / max(total, 1)
    title_ratio = title_count / max(total, 1)
    source_priority = _source_name_priority(column)
    # Colunas com nome forte de categoria podem passar com 50%, mas título de produto
    # ou valores fora do catálogo continuam bloqueados. Isso evita categoria aleatória.
    minimum_safe_ratio = 0.50 if source_priority <= 40 else 0.75
    safe = bool(safe_count and safe_ratio >= minimum_safe_ratio and title_ratio <= 0.20)
    reason = 'categoria validada pelo catálogo controlado'
    if not safe:
        reason = 'categoria bloqueada no mapeamento: ' + '; '.join(invalid_examples or ['sem evidência segura'])
    return {
        'safe': safe,
        'total': total,
        'safe_ratio': round(safe_ratio, 3),
        'title_ratio': round(title_ratio, 3),
        'reason': reason,
    }


def _safe_category_sources(df_source: pd.DataFrame, target_columns: Sequence[str]) -> list[tuple[str, dict[str, object]]]:
    safe: list[tuple[str, dict[str, object]]] = []
    for source in _frame_columns(df_source):
        source_key = normalize_column_key(source)
        name_looks_category = any(normalize_column_key(term) in source_key for term in CATEGORY_SOURCE_PRIORITY + CATEGORY_TARGET_TERMS)
        if not name_looks_category:
            continue
        quality = category_source_quality(df_source, source)
        if bool(quality.get('safe')):
            safe.append((source, quality))
    return sorted(
        safe,
        key=lambda item: (
            _source_name_priority(item[0], target_columns),
            -float(item[1].get('safe_ratio') or 0),
            normalize_text(item[0]),
        ),
    )


def guard_category_mapping(
    source: Any,
    target: Any,
    mapping: Mapping[str, str] | None,
) -> tuple[dict[str, str], list[dict[str, object]]]:
    """Valida o campo Categoria durante o mapeamento usando a mesma trava da categorização.

    O mapeamento não pode aceitar qualquer coluna textual como categoria. Esta função
    só permite fontes que passem pelo catálogo controlado de category_intelligence.py
    e bloqueia títulos de produto, nomes aleatórios, grupo genérico e categoria fora
    do catálogo. Se a etapa de categorização já criou uma coluna segura, ela é
    priorizada automaticamente.
    """
    result = {str(key): str(value or '').strip() for key, value in dict(mapping or {}).items()}
    report: list[dict[str, object]] = []
    if not isinstance(source, pd.DataFrame):
        return result, report

    target_columns = _frame_columns(target)
    category_targets = [target_col for target_col in target_columns if _target_is_category(target_col)]
    if not category_targets:
        return result, report

    safe_sources = _safe_category_sources(source, category_targets)
    best_source = safe_sources[0][0] if safe_sources else ''
    source_columns = set(_frame_columns(source))

    for target_col in category_targets:
        selected = str(result.get(target_col) or '').strip()
        if selected and selected in source_columns:
            quality = category_source_quality(source, selected)
            if bool(quality.get('safe')):
                continue
            replacement = best_source if best_source != selected else ''
            result[target_col] = replacement
            report.append(
                {
                    'target': target_col,
                    'blocked_source': selected,
                    'replacement': replacement,
                    'reason': quality.get('reason') or 'categoria insegura',
                }
            )
            continue
        if not selected and best_source:
            result[target_col] = best_source
            report.append(
                {
                    'target': target_col,
                    'blocked_source': '',
                    'replacement': best_source,
                    'reason': 'categoria segura selecionada automaticamente pelo catálogo controlado',
                }
            )
    return result, report


__all__ = ['category_source_quality', 'guard_category_mapping']
