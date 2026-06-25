from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_guard import validate_category
from bling_app_zero.core.category_intelligence import (
    PROVISIONAL_CATEGORY,
    REVIEW_CATEGORY,
    apply_category_suggestions,
    classify_dataframe,
    ensure_category_column,
    normalize_text,
    suggest_category_for_product,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/category_finalizer.py'
CATEGORY_CONFIDENCE_MIN = 0.80
MAX_REASON_SAMPLE = 80
GUARD_BLOCKING_STATUSES = {'CATEGORY_BLOCKED', 'CATEGORY_FORCED'}

FINAL_CATEGORY_BLOCKLIST = {
    '', 'nan', 'none', 'null', '<na>', 'na', 'n/a',
    'sem categoria', 'revisar manualmente', 'revisao manual',
    'cabos', 'antenas', 'diversos', 'geral', 'outros', 'informatica',
}

OLD_CATEGORY_ALIASES = {
    'microfone': 'Microfones',
    'microfones': 'Microfones',
    'radios am fm': 'Rádios AM e FM',
    'radios am e fm': 'Rádios AM e FM',
    'radio am fm': 'Rádios AM e FM',
    'radio am e fm': 'Rádios AM e FM',
    'power bank': 'Power banks',
    'power banks': 'Power banks',
}

DESCRIPTION_COLS = (
    'Descrição do Produto no Fornecedor', 'Descrição completa', 'Descricao completa',
    'Descrição Complementar', 'Descrição complementar', 'Descricao Complementar', 'Descricao complementar',
    'Descrição Curta', 'Descricao Curta', 'Informações Adicionais', 'Informacoes Adicionais',
    'Características', 'Característica', 'Ficha técnica', 'Ficha tecnica', 'Observações', 'Observacoes',
)
TITLE_COLS = ('Descrição', 'Descricao', 'Nome', 'Nome do produto', 'Produto', 'Título', 'Titulo', 'name', 'nome')
CONTEXT_COLS = ('Categoria origem', 'Grupo de produtos', 'Link Externo', 'URL', 'url', 'Marca', 'Código', 'SKU')


def _filled(value: object) -> bool:
    try:
        if value is None or pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip() != ''


def _join_row(row: pd.Series, columns: tuple[str, ...]) -> str:
    values: list[str] = []
    for col in columns:
        if col in row.index and _filled(row.get(col)):
            values.append(str(row.get(col)))
    return normalize_text(' '.join(values))


def _current_category_bad(value: object) -> bool:
    return normalize_text(value) in FINAL_CATEGORY_BLOCKLIST


def _append_reason(reasons: list[dict[str, Any]], item: dict[str, Any]) -> None:
    if len(reasons) < MAX_REASON_SAMPLE:
        reasons.append(item)


def finalize_categories_for_output(
    df: pd.DataFrame,
    *,
    context: str = 'final_output',
    confidence_min: float = CATEGORY_CONFIDENCE_MIN,
    fallback_unclassified: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aplica a trava final de categorias antes de CSV/API.

    BLINGFIX: não confia em cache, categoria anterior ou item vizinho. A linha é
    revalidada por título, descrição, SKU/modelo e contexto. Quando houver
    conflito, a categoria incompatível é bloqueada e trocada pela categoria real;
    com baixa confiança, cai em Produtos não classificados.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df, {'rows': 0, 'applied': 0, 'forced': 0, 'fallback': 0, 'context': context}

    result, category_col = ensure_category_column(df.copy().fillna(''), preferred='Categoria do produto')
    analyzed, stats = classify_dataframe(result)
    corrected, applied = apply_category_suggestions(
        analyzed,
        confidence_min=confidence_min,
        keep_helper_columns=False,
        fallback_unclassified=fallback_unclassified,
    )
    corrected, category_col = ensure_category_column(corrected.fillna(''), preferred='Categoria do produto')

    forced = 0
    fallback = 0
    alias_fixed = 0
    guard_fixed = 0
    reasons: list[dict[str, Any]] = []

    for idx, row in corrected.iterrows():
        current = str(corrected.at[idx, category_col]).strip()
        norm_current = normalize_text(current)
        if norm_current in OLD_CATEGORY_ALIASES:
            fixed = OLD_CATEGORY_ALIASES[norm_current]
            if fixed != current:
                corrected.at[idx, category_col] = fixed
                current = fixed
                alias_fixed += 1

        description = _join_row(row, DESCRIPTION_COLS)
        title = _join_row(row, TITLE_COLS)
        context_text = _join_row(row, CONTEXT_COLS)

        guard_decision = validate_category(
            title=title,
            description=description,
            current_category=current,
            context=context_text,
        )
        if guard_decision.status in GUARD_BLOCKING_STATUSES and guard_decision.accepted_category and guard_decision.accepted_category != current:
            corrected.at[idx, category_col] = guard_decision.accepted_category
            forced += 1
            guard_fixed += 1
            _append_reason(reasons, {
                'row': int(idx) + 1,
                'from': current,
                'to': guard_decision.accepted_category,
                'confidence': guard_decision.confidence,
                'reason': guard_decision.reason,
                'source': 'category_guard',
            })
            continue

        current = str(corrected.at[idx, category_col]).strip()
        if _current_category_bad(current):
            suggestion = suggest_category_for_product(title, description=description, current_category='')
            if suggestion.category and suggestion.category != REVIEW_CATEGORY and suggestion.confidence >= confidence_min:
                corrected.at[idx, category_col] = suggestion.category
                forced += 1
                _append_reason(reasons, {
                    'row': int(idx) + 1,
                    'from': current,
                    'to': suggestion.category,
                    'confidence': suggestion.confidence,
                    'reason': suggestion.reason,
                })
            elif fallback_unclassified:
                corrected.at[idx, category_col] = PROVISIONAL_CATEGORY
                fallback += 1

    final_empty = 0
    for idx, value in corrected[category_col].fillna('').astype(str).items():
        if _current_category_bad(value):
            corrected.at[idx, category_col] = PROVISIONAL_CATEGORY
            final_empty += 1

    report = {
        'rows': int(len(corrected)),
        'category_column': category_col,
        'applied': int(applied),
        'forced': int(forced),
        'alias_fixed': int(alias_fixed),
        'guard_fixed': int(guard_fixed),
        'fallback_unclassified': int(fallback + final_empty),
        'stats': dict(stats or {}),
        'context': context,
        'sample_reasons': reasons,
        'responsible_file': RESPONSIBLE_FILE,
    }
    try:
        add_audit_event('category_finalizer_applied', area='CATEGORIAS', status='OK', details=report)
    except Exception:
        pass
    return corrected, report


__all__ = ['finalize_categories_for_output']
