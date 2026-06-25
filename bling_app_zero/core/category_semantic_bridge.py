from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from bling_app_zero.core import category_intelligence as ci
from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.smart_column_profiler import profile_as_mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/category_semantic_bridge.py'
TITLE_ALIAS = 'Descrição'
DESCRIPTION_ALIAS = 'Descrição complementar'
CATEGORY_ALIAS = 'Categoria'
_ORIGINAL_CLASSIFY_DATAFRAME = ci.classify_dataframe

TITLE_KINDS = {'descricao', 'descricao_curta', 'nome_apoio'}
DESCRIPTION_KINDS = {'descricao', 'descricao_complementar', 'descricao_curta', 'ficha_tecnica', 'caracteristicas'}
CATEGORY_KINDS = {'categoria'}
CATEGORY_HEADER_TERMS = ('categoria', 'departamento', 'grupo', 'familia', 'família', 'breadcrumb', 'caminho')


def _profile(df: pd.DataFrame, column: str) -> dict[str, Any]:
    try:
        return profile_as_mapping(df, column)
    except Exception:
        return {}


def _header_ok(profile: dict[str, Any], column: str, kinds: set[str]) -> bool:
    header_kind = str(profile.get('header_kind') or infer_kind(column) or '')
    if header_kind in kinds:
        return True
    key = str(column or '').strip().lower()
    if 'categoria' in kinds and any(term in key for term in CATEGORY_HEADER_TERMS):
        return True
    return False


def _content_ok(profile: dict[str, Any], kinds: set[str], prefer: str) -> tuple[bool, float]:
    if not bool(profile.get('has_values')):
        return False, 0.0
    if float(profile.get('price') or 0) >= 0.30:
        return False, 0.0
    if float(profile.get('gtin') or 0) >= 0.40:
        return False, 0.0
    if float(profile.get('ncm') or 0) >= 0.40:
        return False, 0.0
    if float(profile.get('url') or 0) >= 0.25:
        return False, 0.0
    if float(profile.get('image') or 0) >= 0.25:
        return False, 0.0
    content_kind = str(profile.get('content_kind') or profile.get('kind') or '')
    confidence = float(profile.get('confidence') or 0)
    text = float(profile.get('text') or 0)
    avg_len = float(profile.get('avg_len') or 0)
    breadcrumb = float(profile.get('breadcrumb') or 0)
    if content_kind in kinds:
        return True, max(0.70, confidence)
    if prefer in {'title', 'description'} and text >= 0.45 and avg_len >= 5:
        return True, min(0.95, 0.55 + text * 0.25 + min(avg_len, 180) / 600)
    if prefer == 'category' and (breadcrumb >= 0.25 or (text >= 0.45 and avg_len <= 110)):
        return True, min(0.88, max(breadcrumb, text * 0.45 + 0.20))
    return False, 0.0


def _best_column(df: pd.DataFrame, kinds: set[str], *, prefer: str, exclude: set[str] | None = None) -> str:
    exclude = set(exclude or set())
    ranked: list[tuple[float, str]] = []
    for column in [str(c) for c in getattr(df, 'columns', [])]:
        if column in exclude:
            continue
        profile = _profile(df, column)
        if not _header_ok(profile, column, kinds):
            continue
        valid, score = _content_ok(profile, kinds, prefer)
        if valid:
            ranked.append((score, column))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 0.70 else ''


def _validated_detected(df: pd.DataFrame, column: str | None, kinds: set[str], *, prefer: str) -> str | None:
    if not column:
        return None
    profile = _profile(df, str(column))
    if not _header_ok(profile, str(column), kinds):
        return None
    valid, _score = _content_ok(profile, kinds, prefer)
    return str(column) if valid else None


def classify_dataframe_semantic(df: pd.DataFrame, *, category_catalog: Sequence[str] = ci.DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    prepared = df.copy().fillna('')
    temp_columns: set[str] = set()

    title_col = _validated_detected(prepared, ci.detect_product_name_column(prepared), TITLE_KINDS, prefer='title')
    if not title_col and TITLE_ALIAS not in prepared.columns:
        source = _best_column(prepared, TITLE_KINDS, prefer='title')
        if source:
            prepared[TITLE_ALIAS] = prepared[source].fillna('').astype(str)
            temp_columns.add(TITLE_ALIAS)
            title_col = TITLE_ALIAS

    desc_col = _validated_detected(prepared, ci.detect_product_description_column(prepared), DESCRIPTION_KINDS, prefer='description')
    if not desc_col and DESCRIPTION_ALIAS not in prepared.columns:
        source = _best_column(prepared, DESCRIPTION_KINDS, prefer='description', exclude={str(title_col or '')})
        if source:
            prepared[DESCRIPTION_ALIAS] = prepared[source].fillna('').astype(str)
            temp_columns.add(DESCRIPTION_ALIAS)

    category_col = _validated_detected(prepared, ci.detect_category_column(prepared), CATEGORY_KINDS, prefer='category')
    if not category_col and CATEGORY_ALIAS not in prepared.columns:
        source = _best_column(prepared, CATEGORY_KINDS, prefer='category')
        if source:
            prepared[CATEGORY_ALIAS] = prepared[source].fillna('').astype(str)

    result, stats = _ORIGINAL_CLASSIFY_DATAFRAME(prepared, category_catalog=category_catalog)
    removable = [column for column in temp_columns if column in result.columns and column not in getattr(df, 'columns', [])]
    if removable:
        result = result.drop(columns=removable, errors='ignore')
    stats = dict(stats or {})
    stats['semantic_columns_used'] = int(len(temp_columns))
    stats['semantic_rule'] = 'header_confirmed_content_validated'
    return result, stats


__all__ = ['classify_dataframe_semantic']
