from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from bling_app_zero.core import category_intelligence as ci
from bling_app_zero.core.smart_column_profiler import profile_as_mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/category_semantic_bridge.py'
TITLE_ALIAS = 'Descrição'
DESCRIPTION_ALIAS = 'Descrição complementar'
CATEGORY_ALIAS = 'Categoria'


def _profile(df: pd.DataFrame, column: str) -> dict[str, Any]:
    try:
        return profile_as_mapping(df, column)
    except Exception:
        return {}


def _best_column(df: pd.DataFrame, kinds: set[str], *, prefer: str = 'title', exclude: set[str] | None = None) -> str:
    exclude = set(exclude or set())
    ranked: list[tuple[float, str]] = []
    for column in [str(c) for c in getattr(df, 'columns', [])]:
        if column in exclude:
            continue
        profile = _profile(df, column)
        kind = str(profile.get('kind') or '')
        content_kind = str(profile.get('content_kind') or '')
        if kind not in kinds and content_kind not in kinds:
            continue
        if float(profile.get('price') or 0) >= 0.30 or float(profile.get('gtin') or 0) >= 0.40 or float(profile.get('url') or 0) >= 0.25:
            continue
        avg_len = float(profile.get('avg_len') or 0)
        score = float(profile.get('confidence') or 0) + float(profile.get('text') or 0) * 0.25
        if prefer == 'description':
            score += min(avg_len, 240) / 350
        elif prefer == 'category':
            score += float(profile.get('breadcrumb') or 0) * 0.40
        else:
            score += 0.20 if 8 <= avg_len <= 95 else -0.15
        ranked.append((score, column))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 0.62 else ''


def classify_dataframe_semantic(df: pd.DataFrame, *, category_catalog: Sequence[str] = ci.DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    prepared = df.copy().fillna('')
    temp_columns: set[str] = set()
    title_col = ci.detect_product_name_column(prepared)
    if not title_col and TITLE_ALIAS not in prepared.columns:
        source = _best_column(prepared, {'descricao', 'descricao_curta', 'nome_apoio'}, prefer='title')
        if source:
            prepared[TITLE_ALIAS] = prepared[source].fillna('').astype(str)
            temp_columns.add(TITLE_ALIAS)
            title_col = TITLE_ALIAS
    if not ci.detect_product_description_column(prepared) and DESCRIPTION_ALIAS not in prepared.columns:
        source = _best_column(prepared, {'descricao', 'descricao_complementar', 'descricao_curta'}, prefer='description', exclude={str(title_col or '')})
        if source:
            prepared[DESCRIPTION_ALIAS] = prepared[source].fillna('').astype(str)
            temp_columns.add(DESCRIPTION_ALIAS)
    if not ci.detect_category_column(prepared) and CATEGORY_ALIAS not in prepared.columns:
        source = _best_column(prepared, {'categoria'}, prefer='category')
        if source:
            prepared[CATEGORY_ALIAS] = prepared[source].fillna('').astype(str)
    result, stats = ci.classify_dataframe(prepared, category_catalog=category_catalog)
    removable = [column for column in temp_columns if column in result.columns and column not in getattr(df, 'columns', [])]
    if removable:
        result = result.drop(columns=removable, errors='ignore')
    stats = dict(stats or {})
    stats['semantic_columns_used'] = int(len(temp_columns))
    return result, stats


__all__ = ['classify_dataframe_semantic']
