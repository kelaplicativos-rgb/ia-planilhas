from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from bling_app_zero.ai.ai_client import call_openai_json
from bling_app_zero.ai.ai_config import get_ai_settings
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import (
    DEFAULT_CATEGORY_CATALOG,
    PROVISIONAL_CATEGORY,
    REVIEW_CATEGORY,
    CategorySuggestion,
    canonicalize_category,
    classify_dataframe,
    detect_product_description_column,
    detect_product_name_column,
    normalize_text,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/openai_category_fallback.py'
AI_BATCH_SIZE = 30
AI_CONFIDENCE_ACCEPTED = 1.0


def _audit(event: str, *, status: str = 'OK', **details: object) -> None:
    try:
        add_audit_event(event, area='CATEGORIAS', status=status, details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _row_value(row: pd.Series, column: str | None) -> str:
    if not column or column not in row.index:
        return ''
    value = row.get(column, '')
    return '' if value is None else str(value).strip()


def _safe_catalog(catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> list[str]:
    out: list[str] = []
    for category in catalog:
        text = str(category or '').strip()
        if not text or text in {PROVISIONAL_CATEGORY, REVIEW_CATEGORY}:
            continue
        if text not in out:
            out.append(text)
    return out


def _category_from_ai_item(item: dict[str, Any], catalog: Sequence[str]) -> tuple[str, float, str]:
    category = str(item.get('category') or item.get('categoria') or '').strip()
    if not category or category in {REVIEW_CATEGORY, PROVISIONAL_CATEGORY}:
        return '', 0.0, str(item.get('reason') or item.get('motivo') or 'sem categoria real segura')[:220]
    canonical, _changed, reason = canonicalize_category(category, catalog)
    if not canonical or canonical in {PROVISIONAL_CATEGORY, REVIEW_CATEGORY}:
        return '', 0.0, f'categoria fora do catálogo real: {category[:80]}'
    try:
        confidence = float(item.get('confidence') or item.get('confianca') or 0)
    except Exception:
        confidence = 0.0
    if confidence > 1:
        confidence = confidence / 100
    confidence = 1.0 if confidence >= AI_CONFIDENCE_ACCEPTED else max(0.0, min(confidence, 0.99))
    return canonical, confidence, str(item.get('reason') or item.get('motivo') or reason or 'IA real')[:220]


def _call_openai_for_batch(items: list[dict[str, Any]], catalog: Sequence[str]) -> dict[int, CategorySuggestion]:
    if not items:
        return {}
    settings = get_ai_settings()
    if not settings.ready:
        _audit('openai_category_fallback_skipped_not_ready', status='AVISO', rows=len(items), ai_status=settings.status)
        return {}
    instructions = (
        'Classify each product using only one category from the provided catalog. '
        'Use confidence 1.0 only for a fully safe real category. '
        'For uncertain items return category REVISAR MANUALMENTE and confidence 0. '
        'Return JSON: {"items":[{"row":1,"category":"...","confidence":1.0,"reason":"..."}]}.'
    )
    payload = {'catalog': list(catalog), 'items': items}
    result = call_openai_json('openai_category_fallback_v3_all_candidates', instructions, payload, settings=settings)
    if not result.ok:
        _audit('openai_category_fallback_failed', status='AVISO', rows=len(items), error=str(result.error or result.message)[:220])
        return {}
    data = result.data if isinstance(result.data, dict) else {}
    raw_items = data.get('items') if isinstance(data.get('items'), list) else []
    out: dict[int, CategorySuggestion] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            row_id = int(item.get('row'))
        except Exception:
            continue
        category, confidence, reason = _category_from_ai_item(item, catalog)
        if category and confidence >= AI_CONFIDENCE_ACCEPTED:
            out[row_id] = CategorySuggestion(category, 1.0, f'IA real: {reason}', 'CRIAR/VINCULAR')
    _audit('openai_category_fallback_applied_batch', rows=len(items), accepted=len(out), model=settings.model, endpoint='responses')
    return out


def _needs_openai_fallback(row: pd.Series) -> bool:
    category = str(row.get('categoria_sugerida_ia', '') or '').strip()
    action = str(row.get('acao_categoria_ia', '') or '').strip()
    try:
        confidence = float(row.get('confianca_categoria_ia', 0) or 0)
    except Exception:
        confidence = 0.0
    return not category or category == REVIEW_CATEGORY or action == 'REVISAR' or confidence < AI_CONFIDENCE_ACCEPTED


def _row_text_payload(row: pd.Series) -> str:
    return normalize_text(' '.join(str(row.get(col, '')) for col in list(row.index)[:120]))[:1400]


def _apply_unclassified(analyzed: pd.DataFrame, indexes: set[int]) -> int:
    count = 0
    for idx in indexes:
        if idx not in analyzed.index:
            continue
        analyzed.at[idx, 'categoria_sugerida_ia'] = PROVISIONAL_CATEGORY
        analyzed.at[idx, 'acao_categoria_ia'] = 'CRIAR/VINCULAR'
        analyzed.at[idx, 'confianca_categoria_ia'] = 1.0
        analyzed.at[idx, 'motivo_categoria_ia'] = 'Fallback obrigatório: produto sem categoria real segura.'
        count += 1
    return count


def classify_dataframe_with_openai(df: pd.DataFrame, *, category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    analyzed, stats = classify_dataframe(df, category_catalog=category_catalog)
    if not isinstance(analyzed, pd.DataFrame) or analyzed.empty:
        return analyzed, stats
    candidates = analyzed[analyzed.apply(_needs_openai_fallback, axis=1)]
    if candidates.empty:
        return analyzed, {**dict(stats or {}), 'openai_fallback_candidates': 0, 'openai_fallback_applied': 0, 'openai_fallback_unclassified': 0, 'openai_fallback_skipped_no_text': 0}
    catalog = _safe_catalog(category_catalog)
    name_col = detect_product_name_column(analyzed)
    desc_col = detect_product_description_column(analyzed)
    items: list[dict[str, Any]] = []
    skipped_no_text = 0
    for idx, row in candidates.iterrows():
        title = _row_value(row, name_col)
        description = _row_value(row, desc_col)
        row_text = _row_text_payload(row)
        if not title and not description and not row_text:
            skipped_no_text += 1
            continue
        items.append({'row': int(idx), 'title': title[:260], 'description': description[:700], 'row_text': row_text, 'current_category': str(row.get('categoria_atual_ia', '') or '')[:120], 'local_suggestion': str(row.get('categoria_sugerida_ia', '') or '')[:120], 'local_confidence': str(row.get('confianca_categoria_ia', '') or '')})
    accepted: dict[int, CategorySuggestion] = {}
    batches = 0
    for start in range(0, len(items), AI_BATCH_SIZE):
        batches += 1
        accepted.update(_call_openai_for_batch(items[start:start + AI_BATCH_SIZE], catalog))
    for idx, suggestion in accepted.items():
        if idx in analyzed.index:
            analyzed.at[idx, 'categoria_sugerida_ia'] = suggestion.category
            analyzed.at[idx, 'acao_categoria_ia'] = suggestion.action
            analyzed.at[idx, 'confianca_categoria_ia'] = 1.0
            analyzed.at[idx, 'motivo_categoria_ia'] = suggestion.reason
    candidate_indexes = {int(idx) for idx in candidates.index}
    unclassified_count = _apply_unclassified(analyzed, candidate_indexes - {int(idx) for idx in accepted})
    updated_stats = dict(stats or {})
    updated_stats['openai_fallback_candidates'] = int(len(candidates))
    updated_stats['openai_fallback_sent'] = int(len(items))
    updated_stats['openai_fallback_batches'] = int(batches)
    updated_stats['openai_fallback_skipped_no_text'] = int(skipped_no_text)
    updated_stats['openai_fallback_applied'] = int(len(accepted))
    updated_stats['openai_fallback_unclassified'] = int(unclassified_count)
    updated_stats['revisar'] = 0
    _audit('openai_category_fallback_completed_all_candidates', candidates=int(len(candidates)), sent=int(len(items)), batches=int(batches), accepted=int(len(accepted)), fallback_unclassified=int(unclassified_count), skipped_no_text=int(skipped_no_text), no_row_limit=True)
    return analyzed, updated_stats


__all__ = ['classify_dataframe_with_openai']
