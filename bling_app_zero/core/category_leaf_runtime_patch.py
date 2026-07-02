from __future__ import annotations

import re
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/category_leaf_runtime_patch.py'
PATCH_ATTR = '_mapeiaai_category_leaf_runtime_patch_v1'

HIERARCHY_MARKERS = ('>', '»', '›', '→', '|')
EMPTY_VALUES = {'', 'nan', 'none', 'null', '<na>', 'n/a', 'na'}
ROOT_CATEGORY_VALUES = {
    'home',
    'inicio',
    'loja',
    'produtos',
    'produto',
    'todos',
    'todas',
    'categorias',
    'categoria',
    'departamentos',
    'departamento',
    'mais vendidos',
}
CATEGORY_COLUMN_TERMS = (
    'categoria',
    'category',
    'breadcrumb',
    'caminho',
    'departamento',
    'grupo',
    'subgrupo',
    'secao',
    'seção',
    'familia',
    'família',
)
LEAF_PRIORITY_TERMS = (
    'subcategoria',
    'sub categoria',
    'categoria filho',
    'categoria filha',
    'filho',
    'subgrupo',
    'nivel 4',
    'nível 4',
    'nivel 3',
    'nível 3',
    'nivel 2',
    'nível 2',
)


def _audit(event: str, *, status: str = 'OK', **details: object) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='CATEGORIAS', status=status, details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _plain(value: object) -> str:
    return '' if value is None else ' '.join(str(value).replace('\xa0', ' ').split()).strip()


def _norm(value: object) -> str:
    try:
        from bling_app_zero.core.category_intelligence import normalize_text
        return normalize_text(value)
    except Exception:
        return re.sub(r'\s+', ' ', str(value or '').strip().casefold())


def _is_empty(value: object) -> bool:
    return _norm(value) in EMPTY_VALUES


def _split_category_path(value: object) -> list[str]:
    text = _plain(value)
    if not text or _is_empty(text):
        return []
    text = re.sub(r'\s+', ' ', text)

    if any(marker in text for marker in HIERARCHY_MARKERS):
        parts = re.split(r'\s*(?:>|»|›|→|\|)\s*', text)
    elif '\\' in text:
        parts = re.split(r'\s*\\+\s*', text)
    elif '/' in text:
        raw_parts = [part.strip() for part in text.split('/') if part.strip()]
        # Evita quebrar categorias/produtos como AM/FM, A/B, P2/P10 etc.
        if len(raw_parts) >= 3 or any(len(part) > 4 for part in raw_parts[1:]):
            parts = raw_parts
        else:
            parts = [text]
    elif ';' in text:
        raw_parts = [part.strip() for part in text.split(';') if part.strip()]
        parts = raw_parts if len(raw_parts) >= 2 else [text]
    else:
        parts = [text]

    cleaned: list[str] = []
    for part in parts:
        item = _plain(part).strip(' -_/\\|>»›→')
        if not item or _is_empty(item):
            continue
        if _norm(item) in ROOT_CATEGORY_VALUES:
            continue
        cleaned.append(item)
    return cleaned


def extract_category_leaf(value: object) -> str:
    parts = _split_category_path(value)
    return parts[-1] if parts else ''


def _is_category_column_name(column: object) -> bool:
    key = _norm(column)
    return any(term in key for term in CATEGORY_COLUMN_TERMS)


def _is_leaf_priority_column(column: object) -> bool:
    key = _norm(column)
    return any(term in key for term in LEAF_PRIORITY_TERMS)


def _safe_leaf(leaf: str) -> str:
    leaf = _plain(leaf)
    if not leaf or _is_empty(leaf):
        return ''
    norm = _norm(leaf)
    if norm in ROOT_CATEGORY_VALUES:
        return ''
    try:
        from bling_app_zero.core.category_intelligence import BLOCKED_GENERIC_CATEGORIES, PROVISIONAL_CATEGORY_NORMALIZED, looks_like_product_title
        if norm in BLOCKED_GENERIC_CATEGORIES or norm in PROVISIONAL_CATEGORY_NORMALIZED:
            return ''
        if looks_like_product_title(leaf):
            return ''
    except Exception:
        pass
    return leaf


def _leaf_from_row(row: pd.Series) -> tuple[str, str]:
    if not isinstance(row, pd.Series):
        return '', ''
    candidates: list[tuple[int, str, str]] = []
    for pos, column in enumerate(row.index):
        if not _is_category_column_name(column):
            continue
        value = _plain(row.get(column, ''))
        if not value:
            continue
        leaf = _safe_leaf(extract_category_leaf(value))
        if not leaf:
            continue
        priority = 10
        if _is_leaf_priority_column(column):
            priority = 0
        elif any(marker in value for marker in HIERARCHY_MARKERS) or '\\' in value or '/' in value:
            priority = 1
        elif _norm(column) in {'categoria', 'category', 'categoria do produto', 'categoria produto'}:
            priority = 2
        candidates.append((priority, str(column), leaf))
    if not candidates:
        return '', ''
    candidates.sort(key=lambda item: (item[0], -len(item[2])))
    _priority, column, leaf = candidates[0]
    return leaf, column


def _apply_leaf_categories(analyzed: pd.DataFrame, source: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if not isinstance(analyzed, pd.DataFrame) or not isinstance(source, pd.DataFrame):
        return analyzed, 0
    out = analyzed.copy()
    applied = 0
    for idx, row in source.iterrows():
        if idx not in out.index:
            continue
        leaf, column = _leaf_from_row(row)
        if not leaf:
            continue
        try:
            from bling_app_zero.core.category_intelligence import canonicalize_category
            canonical, _changed, _reason = canonicalize_category(leaf)
        except Exception:
            canonical = ''
        final_leaf = canonical or leaf
        out.at[idx, 'categoria_sugerida_ia'] = final_leaf
        out.at[idx, 'acao_categoria_ia'] = 'MANTER' if _norm(final_leaf) == _norm(_plain(row.get(column, ''))) else 'CORRIGIR'
        out.at[idx, 'confianca_categoria_ia'] = 1.0
        out.at[idx, 'motivo_categoria_ia'] = f'Categoria final da origem usada sem OpenAI: {column} → {final_leaf}'
        applied += 1
    return out, applied


def install_category_leaf_runtime_patch() -> bool:
    try:
        from bling_app_zero.core import category_intelligence as ci
    except Exception as exc:
        _audit('category_leaf_runtime_patch_import_failed', status='AVISO', error=str(exc)[:220])
        return False

    if getattr(ci, PATCH_ATTR, False):
        return False

    original_classify_dataframe = ci.classify_dataframe

    def classify_dataframe_leaf_first(df: pd.DataFrame, *, category_catalog=ci.DEFAULT_CATEGORY_CATALOG):
        analyzed, stats = original_classify_dataframe(df, category_catalog=category_catalog)
        analyzed, leaf_applied = _apply_leaf_categories(analyzed, df)
        if leaf_applied:
            stats = dict(stats or {})
            stats['source_category_leaf_applied'] = int(leaf_applied)
            stats['revisar'] = int((analyzed['acao_categoria_ia'] == 'REVISAR').sum()) if 'acao_categoria_ia' in analyzed.columns else int(stats.get('revisar', 0) or 0)
        return analyzed, stats

    ci.classify_dataframe = classify_dataframe_leaf_first
    try:
        from bling_app_zero.core import openai_category_fallback as fallback
        fallback.classify_dataframe = classify_dataframe_leaf_first
    except Exception as exc:
        _audit('category_leaf_runtime_patch_openai_binding_warning', status='AVISO', error=str(exc)[:220])

    setattr(ci, PATCH_ATTR, True)
    _audit('category_leaf_runtime_patch_installed', source_category_leaf_first=True, avoids_openai_when_source_has_leaf=True)
    return True


__all__ = ['extract_category_leaf', 'install_category_leaf_runtime_patch']
