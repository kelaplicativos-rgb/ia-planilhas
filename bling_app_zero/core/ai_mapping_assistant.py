from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

from bling_app_zero.core.mapping_confidence import confidence_for_mapping

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_TARGETS = 120
MAX_SOURCE_COLUMNS = 160
MAX_SAMPLES = 6
SESSION_AI_LIMIT_DEFAULT = 5
SESSION_AI_LIMIT_KEY = 'ai_real_mapping_session_limit'
SESSION_AI_USED_KEY = 'ai_real_mapping_session_used'


@dataclass(frozen=True)
class AIMappingResult:
    enabled: bool
    applied: int
    suggestions: dict[str, str]
    reason: str = ''


def _normalize_header(value: object) -> str:
    text = str(value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _read_streamlit_secret(path: tuple[str, ...]) -> str:
    try:
        import streamlit as st
        current: Any = st.secrets
        for part in path:
            if hasattr(current, 'get'):
                current = current.get(part, '')
            else:
                current = current[part]
            if current in (None, ''):
                return ''
        return str(current or '').strip()
    except Exception:
        return ''


def _get_secret_value(key: str) -> str:
    key = str(key or '').strip()
    if not key:
        return ''
    env_value = os.getenv(key, '')
    if env_value:
        return str(env_value).strip()
    direct = _read_streamlit_secret((key,))
    if direct:
        return direct
    lower_key = key.lower()
    if lower_key == 'openai_api_key':
        for path in (('openai', 'api_key'), ('openai', 'OPENAI_API_KEY'), ('openai', 'key'), ('openai_api_key',), ('api_key',)):
            value = _read_streamlit_secret(path)
            if value:
                return value
    if lower_key == 'openai_model':
        for path in (('openai', 'model'), ('OPENAI_MODEL',), ('openai_model',)):
            value = _read_streamlit_secret(path)
            if value:
                return value
    return ''


def _get_session_limit() -> int:
    try:
        import streamlit as st
        configured = _read_streamlit_secret(('openai', 'session_limit')) or _read_streamlit_secret(('OPENAI_SESSION_LIMIT',))
        limit = int(str(configured or '').strip() or SESSION_AI_LIMIT_DEFAULT)
        st.session_state.setdefault(SESSION_AI_LIMIT_KEY, limit)
        return max(0, int(st.session_state.get(SESSION_AI_LIMIT_KEY) or limit))
    except Exception:
        return SESSION_AI_LIMIT_DEFAULT


def ai_mapping_enabled() -> bool:
    return bool(_get_secret_value('OPENAI_API_KEY'))


def ai_mapping_remaining_session_calls() -> int:
    limit = _get_session_limit()
    try:
        import streamlit as st
        used = int(st.session_state.get(SESSION_AI_USED_KEY, 0) or 0)
        return max(0, limit - used)
    except Exception:
        return limit


def _consume_session_call() -> bool:
    if not ai_mapping_enabled() or ai_mapping_remaining_session_calls() <= 0:
        return False
    try:
        import streamlit as st
        st.session_state[SESSION_AI_USED_KEY] = int(st.session_state.get(SESSION_AI_USED_KEY, 0) or 0) + 1
    except Exception:
        pass
    return True


def _samples(df: pd.DataFrame, column: str, limit: int = MAX_SAMPLES) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    for value in df[column].dropna().astype(str).head(40):
        text = str(value or '').strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            continue
        if len(text) > 120:
            text = text[:120] + '...'
        values.append(text)
        if len(values) >= limit:
            break
    return values


def _column_profile(df: pd.DataFrame, column: str) -> dict[str, Any]:
    samples = _samples(df, column, limit=12)
    joined = ' | '.join(samples).lower()
    digits_only = [re.sub(r'\D+', '', sample) for sample in samples]
    numeric_like = 0
    price_like = 0
    gtin_like = 0
    url_like = 0
    image_like = 0
    integer_like = 0
    month_like = 0

    for raw, digits in zip(samples, digits_only):
        text = str(raw or '').strip().lower()
        if re.fullmatch(r'\d{8}|\d{12}|\d{13}|\d{14}', digits or ''):
            gtin_like += 1
        if re.search(r'https?://|www\.', text):
            url_like += 1
        if re.search(r'\.(jpg|jpeg|png|webp|gif)(\?|$)|cdn|image|imagem|foto', text):
            image_like += 1
        if re.search(r'(r\$|\d+[\.,]\d{2})', text):
            price_like += 1
        if re.fullmatch(r'\d+', digits or ''):
            integer_like += 1
        if re.search(r'\b(mes|meses|garantia)\b', text) or (digits and digits.isdigit() and 0 < int(digits[:4]) <= 120):
            month_like += 1
        if re.search(r'\d', text):
            numeric_like += 1

    count = max(1, len(samples))
    return {
        'samples': samples[:MAX_SAMPLES],
        'sample_count': len(samples),
        'gtin_score': gtin_like / count,
        'url_score': url_like / count,
        'image_score': image_like / count,
        'price_score': price_like / count,
        'integer_score': integer_like / count,
        'month_score': month_like / count,
        'numeric_score': numeric_like / count,
        'text_score': 1.0 if samples and len(joined) > 0 else 0.0,
    }


def _target_kind(target: str) -> str:
    key = _normalize_header(target)
    if any(term in key for term in ['gtin', 'ean', 'codigo barras', 'barra embalagem']):
        return 'gtin'
    if any(term in key for term in ['preco', 'valor', 'custo', 'unitario']):
        return 'price'
    if any(term in key for term in ['url imagem', 'imagem', 'foto']):
        return 'image'
    if any(term in key for term in ['url', 'link']):
        return 'url'
    if any(term in key for term in ['estoque', 'saldo', 'quantidade', 'balanco']):
        return 'stock'
    if any(term in key for term in ['garantia', 'meses garantia']):
        return 'warranty_months'
    if any(term in key for term in ['fornecedor', 'marca', 'categoria', 'descricao', 'nome', 'titulo']):
        return 'text'
    return 'generic'


def _profile_matches_kind(profile: dict[str, Any], kind: str) -> bool:
    if kind == 'gtin':
        return float(profile.get('gtin_score') or 0) >= 0.55
    if kind == 'price':
        return float(profile.get('price_score') or 0) >= 0.45
    if kind == 'image':
        return float(profile.get('image_score') or 0) >= 0.35 or float(profile.get('url_score') or 0) >= 0.65
    if kind == 'url':
        return float(profile.get('url_score') or 0) >= 0.55
    if kind == 'stock':
        return float(profile.get('integer_score') or 0) >= 0.50
    if kind == 'warranty_months':
        return float(profile.get('month_score') or 0) >= 0.45 or float(profile.get('integer_score') or 0) >= 0.70
    if kind == 'text':
        return float(profile.get('text_score') or 0) > 0
    return True


def _exact_header_suggestions(source_columns: list[str], target_columns: list[str]) -> dict[str, str]:
    normalized_sources: dict[str, str] = {}
    for source in source_columns:
        normalized = _normalize_header(source)
        if normalized and normalized not in normalized_sources:
            normalized_sources[normalized] = source

    suggestions: dict[str, str] = {}
    used: set[str] = set()
    for target in target_columns:
        normalized = _normalize_header(target)
        source = normalized_sources.get(normalized, '')
        if source and source not in used:
            suggestions[str(target)] = source
            used.add(source)
    return suggestions


def _content_based_suggestions(df_source: pd.DataFrame, target_columns: list[str], source_columns: list[str]) -> dict[str, str]:
    """Segunda camada: usa conteúdo das linhas quando cabeçalho não resolve."""
    profiles = {source: _column_profile(df_source, source) for source in source_columns}
    suggestions: dict[str, str] = {}
    used: set[str] = set()

    for target in target_columns:
        kind = _target_kind(target)
        if kind == 'generic':
            continue
        candidates: list[tuple[float, str]] = []
        target_key = _normalize_header(target)
        for source in source_columns:
            if source in used:
                continue
            source_key = _normalize_header(source)
            profile = profiles[source]
            if not _profile_matches_kind(profile, kind):
                continue
            name_bonus = 0.0
            if target_key == source_key:
                name_bonus = 1.0
            elif target_key and source_key and (target_key in source_key or source_key in target_key):
                name_bonus = 0.75
            elif any(piece and piece in source_key for piece in target_key.split() if len(piece) >= 4):
                name_bonus = 0.35

            content_score = {
                'gtin': float(profile.get('gtin_score') or 0),
                'price': float(profile.get('price_score') or 0),
                'image': max(float(profile.get('image_score') or 0), float(profile.get('url_score') or 0)),
                'url': float(profile.get('url_score') or 0),
                'stock': float(profile.get('integer_score') or 0),
                'warranty_months': max(float(profile.get('month_score') or 0), float(profile.get('integer_score') or 0)),
                'text': float(profile.get('text_score') or 0),
            }.get(kind, 0.0)
            score = (content_score * 0.70) + (name_bonus * 0.30)
            candidates.append((score, source))

        candidates.sort(reverse=True)
        if candidates and candidates[0][0] >= 0.72:
            suggestions[target] = candidates[0][1]
            used.add(candidates[0][1])
    return suggestions


def _build_payload(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str]) -> dict[str, Any]:
    source_columns = [str(c) for c in list(df_source.columns)[:MAX_SOURCE_COLUMNS]]
    targets = [str(c) for c in target_columns[:MAX_TARGETS]]
    exact_suggestions = _exact_header_suggestions(source_columns, targets)
    content_suggestions = _content_based_suggestions(df_source, targets, source_columns)
    return {
        'task': 'Map target template headers to supplier/source spreadsheet headers using header names and real row content.',
        'priority': [
            '1. If target and source headers are identical after normalization, map them.',
            '2. If header names differ, inspect sample row content and map only when the content type and business meaning match.',
            '3. GTIN/EAN must map only to columns containing GTIN/EAN-like values or matching GTIN/EAN headers.',
            '4. Price must map only to monetary values or matching price/cost headers.',
            '5. Warranty months must map only to month/garantia numeric columns.',
            '6. Use exact source column names from source_columns. Never invent source columns.',
            '7. If unsure, return empty string.',
        ],
        'examples': {
            'Fornecedor': 'Fornecedor',
            'Meses Garantia no Fornecedor': 'Meses Garantia no Fornecedor',
            'GTIN/EAN da embalagem': 'GTIN/EAN da embalagem',
        },
        'response_format': 'Return only JSON object: {"mapping": {target_column: source_column_or_empty_string}}.',
        'target_columns': targets,
        'source_columns': [
            {
                'name': column,
                'normalized_name': _normalize_header(column),
                'profile': _column_profile(df_source, column),
            }
            for column in source_columns
        ],
        'current_mapping': {str(k): str(v or '') for k, v in dict(current_mapping or {}).items() if str(k) in targets},
        'precomputed_exact_header_matches': exact_suggestions,
        'precomputed_content_matches': content_suggestions,
    }


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = str(text or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?', '', cleaned, flags=re.I).strip()
        cleaned = re.sub(r'```$', '', cleaned).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    match = re.search(r'\{.*\}', cleaned, flags=re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _call_openai(payload: dict[str, Any]) -> dict[str, str]:
    api_key = _get_secret_value('OPENAI_API_KEY')
    if not api_key:
        return {}
    model = _get_secret_value('OPENAI_MODEL') or DEFAULT_MODEL
    body = {
        'model': model,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are a precise spreadsheet mapping assistant. '
                    'Correlate template headers with supplier headers using both header names and sample row content. '
                    'Be conservative. Return JSON only.'
                ),
            },
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
        ],
    }
    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=body,
            timeout=18.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        parsed = _extract_json(content)
        mapping = parsed.get('mapping', {}) if isinstance(parsed, dict) else {}
        if not isinstance(mapping, dict):
            return {}
        return {str(k): str(v or '') for k, v in mapping.items()}
    except Exception:
        return {}


def _needs_ai(target: str, current_mapping: dict[str, str], df_source: pd.DataFrame) -> bool:
    selected = str(current_mapping.get(target, '') or '')
    if not selected:
        return True
    info = confidence_for_mapping(df_source, target, selected)
    return str(info.get('level')) in {'vermelho', 'amarelo'}


def _valid_source(source: str, source_columns: set[str]) -> bool:
    return bool(source) and source in source_columns


def _accept_suggestions(suggestions: dict[str, str], targets: list[str], source_columns: set[str], current_mapping: dict[str, str], df_source: pd.DataFrame) -> dict[str, str]:
    accepted: dict[str, str] = {}
    used = {value for value in dict(current_mapping or {}).values() if value}
    for target, source in suggestions.items():
        target = str(target)
        source = str(source or '')
        if target not in targets or not _valid_source(source, source_columns):
            continue
        if source in used and current_mapping.get(target) != source:
            continue
        if _normalize_header(target) == _normalize_header(source):
            accepted[target] = source
            used.add(source)
            continue
        if _profile_matches_kind(_column_profile(df_source, source), _target_kind(target)):
            accepted[target] = source
            used.add(source)
            continue
        info = confidence_for_mapping(df_source, target, source)
        if str(info.get('level')) == 'verde':
            accepted[target] = source
            used.add(source)
    return accepted


def apply_ai_mapping_assist(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str], only_uncertain: bool = True) -> AIMappingResult:
    if not ai_mapping_enabled():
        return AIMappingResult(False, 0, {}, 'OPENAI_API_KEY ausente')
    if ai_mapping_remaining_session_calls() <= 0:
        return AIMappingResult(False, 0, {}, 'limite de IA da sessão atingido')
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return AIMappingResult(True, 0, {}, 'origem vazia')

    source_columns_list = [str(c) for c in df_source.columns]
    source_columns = set(source_columns_list)
    all_targets = [str(t) for t in target_columns]
    targets = all_targets
    if only_uncertain:
        targets = [target for target in all_targets if _needs_ai(target, current_mapping, df_source)]
    if not targets:
        return AIMappingResult(True, 0, {}, 'sem campos incertos')

    exact = _exact_header_suggestions(source_columns_list, targets)
    content = _content_based_suggestions(df_source, targets, source_columns_list)

    if not _consume_session_call():
        fallback = {**content, **exact}
        return AIMappingResult(False, len(fallback), fallback, 'limite de IA da sessão atingido')

    payload = _build_payload(df_source, targets, current_mapping)
    ai_suggestions = _call_openai(payload)
    combined = {**ai_suggestions, **content, **exact}
    if not combined:
        return AIMappingResult(True, 0, {}, 'sem sugestoes da IA')

    accepted = _accept_suggestions(combined, targets, source_columns, current_mapping, df_source)
    return AIMappingResult(True, len(accepted), accepted, 'ok')


def merge_ai_suggestions(current_mapping: dict[str, str], ai_result: AIMappingResult) -> dict[str, str]:
    merged = dict(current_mapping or {})
    for target, source in dict(ai_result.suggestions or {}).items():
        merged[target] = source
    return merged
