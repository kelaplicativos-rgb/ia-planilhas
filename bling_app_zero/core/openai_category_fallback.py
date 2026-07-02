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
MAX_AI_ROWS = 120
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
        if not text or text == PROVISIONAL_CATEGORY or text == REVIEW_CATEGORY:
            continue
        if text not in out:
            out.append(text)
    return out


def _category_from_ai_item(item: dict[str, Any], catalog: Sequence[str]) -> tuple[str, float, str]:
    category = str(item.get('category') or item.get('categoria') or '').strip()
    if not category or category == REVIEW_CATEGORY:
        return '', 0.0, str(item.get('reason') or item.get('motivo') or 'sem categoria segura')[:220]
    canonical, _changed, reason = canonicalize_category(category, catalog)
    if not canonical or canonical in {PROVISIONAL_CATEGORY, REVIEW_CATEGORY}:
        return '', 0.0, f'OpenAI retornou categoria fora do catálogo: {category[:80]}'
    try:
        confidence = float(item.get('confidence') or item.get('confianca') or 0)
    except Exception:
        confidence = 0.0
    if confidence > 1:
        confidence = confidence / 100
    confidence = 1.0 if confidence >= AI_CONFIDENCE_ACCEPTED else max(0.0, min(confidence, 0.99))
    ai_reason = str(item.get('reason') or item.get('motivo') or reason or 'OpenAI real')[:220]
    return canonical, confidence, ai_reason


def _call_openai_for_batch(items: list[dict[str, Any]], catalog: Sequence[str]) -> dict[int, CategorySuggestion]:
    if not items:
        return {}
    settings = get_ai_settings()
    if not settings.ready:
        _audit('openai_category_fallback_skipped_not_ready', status='AVISO', rows=len(items), ai_status=settings.status)
        return {}

    instructions = (
        'Você é a IA real de categorização do MapeiaAI. Classifique produtos de loja de eletrônicos e utilidades. '
        'Use somente uma categoria existente no catálogo recebido. Nunca invente categoria nova. '
        'Retorne confidence 1.0 apenas quando a categoria estiver totalmente segura pelo título/descrição. '
        'Se houver dúvida, retorne category "REVISAR MANUALMENTE" e confidence 0. '
        'Responda JSON no formato {"items":[{"row":1,"category":"...","confidence":1.0,"reason":"..."}]}.'
    )
    payload = {
        'catalog': list(catalog),
        'rules': [
            'Escolher somente categoria do catálogo.',
            'Não usar nome/modelo do produto como categoria.',
            'Não usar categoria genérica quando houver dúvida.',
            'confidence 1.0 significa certeza máxima; abaixo disso será rejeitado.',
        ],
        'items': items,
    }
    result = call_openai_json('openai_category_fallback_v1', instructions, payload, settings=settings)
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
        if not category or confidence < AI_CONFIDENCE_ACCEPTED:
            continue
        out[row_id] = CategorySuggestion(category, 1.0, f'OpenAI real: {reason}', 'CRIAR/VINCULAR')
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


def classify_dataframe_with_openai(df: pd.DataFrame, *, category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    analyzed, stats = classify_dataframe(df, category_catalog=category_catalog)
    if not isinstance(analyzed, pd.DataFrame) or analyzed.empty:
        return analyzed, stats

    candidates = analyzed[analyzed.apply(_needs_openai_fallback, axis=1)]
    if candidates.empty:
        return analyzed, {**dict(stats or {}), 'openai_fallback_candidates': 0, 'openai_fallback_applied': 0}

    catalog = _safe_catalog(category_catalog)
    name_col = detect_product_name_column(analyzed)
    desc_col = detect_product_description_column(analyzed)
    items: list[dict[str, Any]] = []
    for idx, row in candidates.head(MAX_AI_ROWS).iterrows():
        title = _row_value(row, name_col)
        description = _row_value(row, desc_col)
        if not title and not description:
            continue
        items.append({
            'row': int(idx),
            'title': title[:260],
            'description': description[:700],
            'current_category': str(row.get('categoria_atual_ia', '') or '')[:120],
            'local_suggestion': str(row.get('categoria_sugerida_ia', '') or '')[:120],
            'local_confidence': str(row.get('confianca_categoria_ia', '') or ''),
            'row_text': normalize_text(' '.join(str(row.get(col, '')) for col in list(row.index)[:80]))[:1000],
        })

    accepted: dict[int, CategorySuggestion] = {}
    for start in range(0, len(items), AI_BATCH_SIZE):
        batch = items[start:start + AI_BATCH_SIZE]
        accepted.update(_call_openai_for_batch(batch, catalog))

    for idx, suggestion in accepted.items():
        if idx not in analyzed.index:
            continue
        analyzed.at[idx, 'categoria_sugerida_ia'] = suggestion.category
        analyzed.at[idx, 'acao_categoria_ia'] = suggestion.action
        analyzed.at[idx, 'confianca_categoria_ia'] = 1.0
        analyzed.at[idx, 'motivo_categoria_ia'] = suggestion.reason

    updated_stats = dict(stats or {})
    updated_stats['openai_fallback_candidates'] = int(len(candidates))
    updated_stats['openai_fallback_sent'] = int(len(items))
    updated_stats['openai_fallback_applied'] = int(len(accepted))
    updated_stats['revisar'] = int((analyzed['acao_categoria_ia'] == 'REVISAR').sum()) if 'acao_categoria_ia' in analyzed.columns else int(updated_stats.get('revisar', 0) or 0)
    _audit('openai_category_fallback_completed', candidates=int(len(candidates)), sent=int(len(items)), accepted=int(len(accepted)))
    return analyzed, updated_stats


__all__ = ['classify_dataframe_with_openai']
