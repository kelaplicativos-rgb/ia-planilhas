from __future__ import annotations

import json
import re
from typing import Any

from bling_app_zero.core.ai_runtime_context import get_secret_value
from bling_app_zero.core.ncm.ncm_catalog import NCM_CATALOG_RULES, NcmCatalogRule
from bling_app_zero.core.ncm.ncm_types import EMPTY_NCM_SUGGESTION, NcmSuggestion
from bling_app_zero.core.text import normalize_key

NCM_RE = re.compile(r'\b\d{8}\b')


def _clean_ncm(value: Any) -> str:
    digits = re.sub(r'\D+', '', str(value or ''))
    return digits if len(digits) == 8 else ''


def _product_text(row: dict[str, Any]) -> str:
    preferred_terms = ('descricao', 'descrição', 'nome', 'produto', 'titulo', 'título', 'categoria', 'marca')
    parts: list[str] = []
    for key, value in row.items():
        key_norm = normalize_key(key)
        if any(term in key_norm for term in preferred_terms):
            text = str(value or '').strip()
            if text:
                parts.append(text)
    if not parts:
        parts = [str(value or '').strip() for value in row.values() if str(value or '').strip()]
    return ' '.join(parts)[:1800]


def _keyword_score(text_key: str, rule: NcmCatalogRule) -> int:
    if any(normalize_key(term) in text_key for term in rule.negative_keywords):
        return 0
    hits = [term for term in rule.keywords if normalize_key(term) in text_key]
    if not hits:
        return 0
    bonus = min(12, max(0, len(hits) - 1) * 4)
    return min(98, rule.base_score + bonus)


def _catalog_suggestion(row: dict[str, Any]) -> NcmSuggestion:
    text = _product_text(row)
    text_key = normalize_key(text)
    best_rule: NcmCatalogRule | None = None
    best_score = 0
    for rule in NCM_CATALOG_RULES:
        score = _keyword_score(text_key, rule)
        if score > best_score:
            best_rule = rule
            best_score = score
    if not best_rule or not best_rule.ncm:
        return EMPTY_NCM_SUGGESTION
    confidence = 'alta' if best_score >= 82 else 'media' if best_score >= 70 else 'baixa'
    return NcmSuggestion(
        ncm=best_rule.ncm,
        confidence=confidence,
        score=best_score,
        source='catalogo_local',
        reason=f'{best_rule.label}. Sugestão por palavras-chave do produto.',
    )


def _openai_api_key() -> str:
    return get_secret_value('OPENAI_API_KEY') or get_secret_value('openai_api_key')


def _ai_suggestion(row: dict[str, Any]) -> NcmSuggestion:
    api_key = _openai_api_key()
    if not api_key:
        return EMPTY_NCM_SUGGESTION
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        product_text = _product_text(row)
        prompt = (
            'Você é um assistente fiscal para sugestão preliminar de NCM no Brasil. '
            'Responda somente JSON válido com as chaves ncm, confidence, score e reason. '
            'Use confidence alta, media ou baixa. Nunca invente se não houver segurança. '
            'NCM precisa ter 8 dígitos. Produto: '
            f'{product_text}'
        )
        response = client.chat.completions.create(
            model=get_secret_value('OPENAI_MODEL') or 'gpt-4o-mini',
            temperature=0,
            messages=[
                {'role': 'system', 'content': 'Sugira NCM apenas como apoio revisável, nunca como certeza fiscal.'},
                {'role': 'user', 'content': prompt},
            ],
        )
        raw = response.choices[0].message.content or '{}'
        payload = json.loads(raw)
        ncm = _clean_ncm(payload.get('ncm'))
        confidence = str(payload.get('confidence') or 'baixa').lower().strip()
        if confidence not in {'alta', 'media', 'baixa'}:
            confidence = 'baixa'
        score = int(payload.get('score') or 0)
        reason = str(payload.get('reason') or 'Sugestão da IA para revisão.').strip()
        if not ncm:
            return EMPTY_NCM_SUGGESTION
        return NcmSuggestion(ncm=ncm, confidence=confidence, score=max(0, min(100, score)), source='openai', reason=reason)
    except Exception:
        return EMPTY_NCM_SUGGESTION


def suggest_ncm_for_product(row: dict[str, Any], *, use_ai: bool = True) -> NcmSuggestion:
    catalog = _catalog_suggestion(row)
    if catalog.should_apply or not use_ai:
        return catalog
    ai = _ai_suggestion(row)
    if ai.score > catalog.score:
        return ai
    return catalog


__all__ = ['suggest_ncm_for_product']
