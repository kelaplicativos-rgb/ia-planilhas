from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

from bling_app_zero.core.ai_runtime_context import consume_ai_session_call, get_secret_value
from bling_app_zero.core.mapping_confidence import confidence_for_mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/ai_mapping_executor.py'
OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_SOURCE_COLUMNS = 160
MAX_TARGETS = 120
MAX_SAMPLES = 6


@dataclass(frozen=True)
class AIMappingExecutionResult:
    enabled: bool
    applied: int
    suggestions: dict[str, str]
    reason: str = ''


def normalize_header(value: object) -> str:
    text = str(value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def samples(df: pd.DataFrame, column: str, limit: int = MAX_SAMPLES) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    for value in df[column].dropna().astype(str).head(60):
        text = str(value or '').strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            continue
        values.append(text[:160] + ('...' if len(text) > 160 else ''))
        if len(values) >= limit:
            break
    return values


def number_from_text(value: str) -> float | None:
    text = re.sub(r'[^0-9,.-]+', '', str(value or '').strip())
    if not text:
        return None
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return None


def is_integer_quantity_text(value: str) -> bool:
    text = str(value or '').strip().lower()
    if not text or any(token in text for token in ['r$', '$', '€', 'preco', 'preço', 'valor']):
        return False
    if re.search(r'\d+[\.,]\d{1,4}', text):
        return False
    digits = re.sub(r'\D+', '', text)
    if not digits:
        return False
    try:
        number = int(digits)
    except Exception:
        return False
    return 0 <= number <= 1_000_000 and len(digits) <= 7


def column_profile(df: pd.DataFrame, column: str) -> dict[str, Any]:
    raw_samples = samples(df, column, limit=12)
    digits_only = [re.sub(r'\D+', '', sample) for sample in raw_samples]
    count = max(1, len(raw_samples))
    scores = {
        'gtin_score': 0,
        'url_score': 0,
        'image_score': 0,
        'price_score': 0,
        'money_decimal_score': 0,
        'integer_score': 0,
        'stock_quantity_score': 0,
        'text_score': 1.0 if raw_samples else 0.0,
    }
    for raw, digits in zip(raw_samples, digits_only):
        text = str(raw or '').strip().lower()
        number = number_from_text(text)
        has_money_marker = bool(re.search(r'(r\$|\$|€|preco|preço|valor)', text))
        has_decimal = bool(re.search(r'\d+[\.,]\d{1,4}', text))
        if re.fullmatch(r'\d{8}|\d{12}|\d{13}|\d{14}', digits or ''):
            scores['gtin_score'] += 1
        if re.search(r'https?://|www\.', text):
            scores['url_score'] += 1
        if re.search(r'\.(jpg|jpeg|png|webp|gif)(\?|$)|cdn|image|imagem|foto', text):
            scores['image_score'] += 1
        if has_money_marker or (has_decimal and number is not None and 0 <= number <= 1_000_000):
            scores['price_score'] += 1
        if has_money_marker or has_decimal:
            scores['money_decimal_score'] += 1
        if re.fullmatch(r'\d+', digits or '') and not has_decimal:
            scores['integer_score'] += 1
        if is_integer_quantity_text(text):
            scores['stock_quantity_score'] += 1
    for key in list(scores.keys()):
        if key.endswith('_score') and key != 'text_score':
            scores[key] = float(scores[key]) / count
    return {'samples': raw_samples[:MAX_SAMPLES], **scores}


def target_kind(target: str) -> str:
    key = normalize_header(target)
    if any(term in key for term in ['gtin', 'ean', 'codigo barras', 'barra embalagem']):
        return 'gtin'
    if any(term in key for term in ['estoque', 'saldo', 'quantidade', 'balanco']):
        return 'stock'
    if any(term in key for term in ['preco', 'valor', 'custo', 'unitario']):
        return 'price'
    if any(term in key for term in ['url imagem', 'imagem', 'foto']):
        return 'image'
    if any(term in key for term in ['url', 'link']):
        return 'url'
    if any(term in key for term in ['fornecedor', 'marca', 'categoria', 'descricao', 'nome', 'titulo']):
        return 'text'
    return 'generic'


def header_matches_kind(source: str, kind: str) -> bool:
    key = normalize_header(source)
    if kind == 'stock':
        return any(term in key for term in ['estoque', 'saldo', 'quantidade', 'qtd', 'balanco'])
    if kind == 'price':
        return any(term in key for term in ['preco', 'valor', 'custo', 'unitario'])
    if kind == 'gtin':
        return any(term in key for term in ['gtin', 'ean', 'codigo barras', 'barra'])
    if kind == 'image':
        return any(term in key for term in ['imagem', 'foto', 'url imagem'])
    if kind == 'url':
        return any(term in key for term in ['url', 'link'])
    return True


def profile_matches_kind(profile: dict[str, Any], kind: str, source: str = '') -> bool:
    if kind == 'gtin':
        return float(profile.get('gtin_score') or 0) >= 0.55 or (header_matches_kind(source, kind) and float(profile.get('integer_score') or 0) >= 0.5)
    if kind == 'price':
        return float(profile.get('price_score') or 0) >= 0.45 or header_matches_kind(source, kind)
    if kind == 'image':
        return float(profile.get('image_score') or 0) >= 0.35 or float(profile.get('url_score') or 0) >= 0.65
    if kind == 'url':
        return float(profile.get('url_score') or 0) >= 0.55
    if kind == 'stock':
        if float(profile.get('money_decimal_score') or 0) >= 0.35:
            return False
        return float(profile.get('stock_quantity_score') or 0) >= 0.55 or (header_matches_kind(source, kind) and float(profile.get('integer_score') or 0) >= 0.5)
    if kind == 'text':
        return float(profile.get('text_score') or 0) > 0
    return True


def local_suggestions(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str]) -> dict[str, str]:
    source_columns = [str(column) for column in list(df_source.columns)[:MAX_SOURCE_COLUMNS]]
    source_by_key = {normalize_header(source): source for source in source_columns}
    profiles = {source: column_profile(df_source, source) for source in source_columns}
    used = {str(value) for value in dict(current_mapping or {}).values() if value}
    suggestions: dict[str, str] = {}
    for target in [str(item) for item in target_columns[:MAX_TARGETS]]:
        target_key = normalize_header(target)
        kind = target_kind(target)
        direct = source_by_key.get(target_key)
        if direct and direct not in used and profile_matches_kind(profiles[direct], kind, direct):
            suggestions[target] = direct
            used.add(direct)
            continue
        candidates: list[tuple[float, str]] = []
        for source in source_columns:
            if source in used:
                continue
            source_key = normalize_header(source)
            if not profile_matches_kind(profiles[source], kind, source):
                continue
            name_score = 0.0
            if target_key and (target_key in source_key or source_key in target_key):
                name_score = 0.90
            elif header_matches_kind(source, kind):
                name_score = 0.80
            elif any(piece in source_key for piece in target_key.split() if len(piece) >= 4):
                name_score = 0.40
            content_score = {
                'gtin': float(profiles[source].get('gtin_score') or 0),
                'price': float(profiles[source].get('price_score') or 0),
                'image': max(float(profiles[source].get('image_score') or 0), float(profiles[source].get('url_score') or 0)),
                'url': float(profiles[source].get('url_score') or 0),
                'stock': float(profiles[source].get('stock_quantity_score') or 0),
                'text': float(profiles[source].get('text_score') or 0),
            }.get(kind, 0.0)
            score = (content_score * 0.70) + (name_score * 0.30)
            candidates.append((score, source))
        candidates.sort(reverse=True)
        if candidates and candidates[0][0] >= 0.72:
            suggestions[target] = candidates[0][1]
            used.add(candidates[0][1])
    return suggestions


def extract_json(text: str) -> dict[str, Any]:
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


def openai_suggestions(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str]) -> dict[str, str]:
    api_key = get_secret_value('OPENAI_API_KEY')
    if not api_key:
        return {}
    if not consume_ai_session_call():
        return {}
    source_columns = [str(column) for column in list(df_source.columns)[:MAX_SOURCE_COLUMNS]]
    targets = [str(column) for column in target_columns[:MAX_TARGETS]]
    payload = {
        'task': 'Map target template headers to exact source spreadsheet headers. Return JSON only.',
        'rules': [
            'Use exact source column names only.',
            'Never map stock/quantity to price/cost/value columns.',
            'If unsure, return empty string for that target.',
        ],
        'target_columns': targets,
        'source_columns': [
            {'name': source, 'normalized_name': normalize_header(source), 'profile': column_profile(df_source, source)}
            for source in source_columns
        ],
        'current_mapping': {str(k): str(v or '') for k, v in dict(current_mapping or {}).items()},
    }
    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': get_secret_value('OPENAI_MODEL') or DEFAULT_MODEL,
                'temperature': 0,
                'response_format': {'type': 'json_object'},
                'messages': [
                    {'role': 'system', 'content': 'You are a conservative spreadsheet mapping assistant. Return only JSON.'},
                    {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
                ],
            },
            timeout=18.0,
        )
        response.raise_for_status()
        content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        mapping = extract_json(content).get('mapping', {})
        return {str(k): str(v or '') for k, v in dict(mapping or {}).items()}
    except Exception:
        return {}


def accept_suggestions(suggestions: dict[str, str], df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str]) -> dict[str, str]:
    source_columns = {str(column) for column in df_source.columns}
    targets = {str(column) for column in target_columns}
    used = {str(value) for value in dict(current_mapping or {}).values() if value}
    accepted: dict[str, str] = {}
    for target, source in dict(suggestions or {}).items():
        target = str(target)
        source = str(source or '')
        if target not in targets or source not in source_columns:
            continue
        if source in used and current_mapping.get(target) != source:
            continue
        kind = target_kind(target)
        if not profile_matches_kind(column_profile(df_source, source), kind, source):
            continue
        info = confidence_for_mapping(df_source, target, source)
        level = str(info.get('level') or '')
        if level == 'verde' or normalize_header(target) == normalize_header(source) or header_matches_kind(source, kind):
            accepted[target] = source
            used.add(source)
    return accepted


def execute_ai_mapping(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str], only_uncertain: bool = False) -> AIMappingExecutionResult:
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return AIMappingExecutionResult(True, 0, {}, 'origem vazia')
    targets = [str(target) for target in target_columns]
    if only_uncertain:
        targets = [target for target in targets if not str(current_mapping.get(target, '') or '')]
    if not targets:
        return AIMappingExecutionResult(True, 0, {}, 'sem campos incertos')
    local = local_suggestions(df_source, targets, current_mapping)
    remote = openai_suggestions(df_source, targets, current_mapping)
    combined = {**remote, **local}
    accepted = accept_suggestions(combined, df_source, targets, current_mapping)
    if not accepted:
        return AIMappingExecutionResult(True, 0, {}, 'sem sugestoes seguras')
    return AIMappingExecutionResult(True, len(accepted), accepted, 'ok')


__all__ = [
    'AIMappingExecutionResult',
    'RESPONSIBLE_FILE',
    'accept_suggestions',
    'column_profile',
    'execute_ai_mapping',
    'local_suggestions',
    'normalize_header',
    'openai_suggestions',
]
