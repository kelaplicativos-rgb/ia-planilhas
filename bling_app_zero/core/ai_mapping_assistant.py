from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

from bling_app_zero.core.mapping_confidence import confidence_for_mapping

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_TARGETS = 45
MAX_SOURCE_COLUMNS = 80
MAX_SAMPLES = 4
SESSION_AI_LIMIT_DEFAULT = 5
SESSION_AI_LIMIT_KEY = 'ai_real_mapping_session_limit'
SESSION_AI_USED_KEY = 'ai_real_mapping_session_used'


@dataclass(frozen=True)
class AIMappingResult:
    enabled: bool
    applied: int
    suggestions: dict[str, str]
    reason: str = ''


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
    """Lê somente a chave do app/admin, nunca uma chave digitada pelo usuário final.

    Formatos aceitos no Streamlit Secrets:
    OPENAI_API_KEY = "..."
    OPENAI_MODEL = "..."

    ou:

    [openai]
    api_key = "..."
    model = "gpt-4o-mini"
    session_limit = 5
    """
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
        for path in (
            ('openai', 'api_key'),
            ('openai', 'OPENAI_API_KEY'),
            ('openai', 'key'),
            ('openai_api_key',),
            ('api_key',),
        ):
            value = _read_streamlit_secret(path)
            if value:
                return value

    if lower_key == 'openai_model':
        for path in (
            ('openai', 'model'),
            ('OPENAI_MODEL',),
            ('openai_model',),
        ):
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
    if not ai_mapping_enabled():
        return False
    remaining = ai_mapping_remaining_session_calls()
    if remaining <= 0:
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
    for value in df[column].dropna().astype(str).head(30):
        text = str(value or '').strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            continue
        if len(text) > 120:
            text = text[:120] + '...'
        values.append(text)
        if len(values) >= limit:
            break
    return values


def _build_payload(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str]) -> dict[str, Any]:
    source_columns = [str(c) for c in list(df_source.columns)[:MAX_SOURCE_COLUMNS]]
    targets = [str(c) for c in target_columns[:MAX_TARGETS]]
    return {
        'rules': [
            'Return only JSON object: {"mapping": {target_column: source_column_or_empty_string}}.',
            'Use exact same source column names. Do not invent source columns.',
            'If unsure, return empty string for that target.',
            'Never map a source column if its sample values are not compatible with the target meaning.',
            'Prefer exact name matches, normalized matches, and semantically equivalent names.',
            'Do not map dimensions, tax, stock, price, GTIN, images, or URL unless values match the expected type.',
        ],
        'target_columns': targets,
        'source_columns': [
            {'name': column, 'samples': _samples(df_source, column)} for column in source_columns
        ],
        'current_mapping': {str(k): str(v or '') for k, v in dict(current_mapping or {}).items() if str(k) in targets},
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
                'content': 'You are a careful data mapping assistant for Brazilian ecommerce spreadsheets and Bling import templates. Be conservative and precise.',
            },
            {
                'role': 'user',
                'content': json.dumps(payload, ensure_ascii=False),
            },
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


def apply_ai_mapping_assist(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    only_uncertain: bool = True,
) -> AIMappingResult:
    if not ai_mapping_enabled():
        return AIMappingResult(False, 0, {}, 'OPENAI_API_KEY ausente')
    if ai_mapping_remaining_session_calls() <= 0:
        return AIMappingResult(False, 0, {}, 'limite de IA da sessão atingido')
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return AIMappingResult(True, 0, {}, 'origem vazia')

    source_columns = {str(c) for c in df_source.columns}
    targets = [str(t) for t in target_columns]
    if only_uncertain:
        targets = [target for target in targets if _needs_ai(target, current_mapping, df_source)]
    if not targets:
        return AIMappingResult(True, 0, {}, 'sem campos incertos')

    if not _consume_session_call():
        return AIMappingResult(False, 0, {}, 'limite de IA da sessão atingido')

    payload = _build_payload(df_source, targets, current_mapping)
    suggestions = _call_openai(payload)
    if not suggestions:
        return AIMappingResult(True, 0, {}, 'sem sugestoes da IA')

    accepted: dict[str, str] = {}
    used = {value for value in dict(current_mapping or {}).values() if value}
    for target, source in suggestions.items():
        target = str(target)
        source = str(source or '')
        if target not in targets or not _valid_source(source, source_columns):
            continue
        if source in used and current_mapping.get(target) != source:
            continue
        info = confidence_for_mapping(df_source, target, source)
        if str(info.get('level')) in {'verde', 'amarelo'}:
            accepted[target] = source
            used.add(source)

    return AIMappingResult(True, len(accepted), accepted, 'ok')


def merge_ai_suggestions(current_mapping: dict[str, str], ai_result: AIMappingResult) -> dict[str, str]:
    merged = dict(current_mapping or {})
    for target, source in dict(ai_result.suggestions or {}).items():
        merged[target] = source
    return merged
