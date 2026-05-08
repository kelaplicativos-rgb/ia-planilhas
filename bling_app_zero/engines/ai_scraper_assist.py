from __future__ import annotations

import json
import os
from typing import Iterable

import httpx
import streamlit as st

from bling_app_zero.core.column_contract import RequestedField
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_CONTEXT_CHARS = 12000


def _unique_names(*names: str) -> list[str]:
    result: list[str] = []
    for name in names:
        for candidate in [name, str(name).upper(), str(name).lower()]:
            if candidate and candidate not in result:
                result.append(candidate)
    return result


def _secret_value(*names: str) -> str:
    expanded_names = _unique_names(*names)

    for name in expanded_names:
        value = os.getenv(name)
        if value:
            return str(value).strip()

    try:
        for name in expanded_names:
            if name in st.secrets:
                value = st.secrets.get(name)
                if value:
                    return str(value).strip()
    except Exception:
        pass

    try:
        openai_section = st.secrets.get('openai', {})
        if isinstance(openai_section, dict):
            for name in expanded_names:
                if name in openai_section and openai_section.get(name):
                    return str(openai_section.get(name) or '').strip()

            wants_key = any('key' in normalize_key(name) or 'token' in normalize_key(name) for name in expanded_names)
            wants_model = any('model' in normalize_key(name) for name in expanded_names)

            if wants_key:
                for alias in ['api_key', 'key', 'token', 'OPENAI_API_KEY', 'openai_api_key']:
                    if alias in openai_section and openai_section.get(alias):
                        return str(openai_section.get(alias) or '').strip()

            if wants_model:
                for alias in ['model', 'OPENAI_MODEL', 'openai_model']:
                    if alias in openai_section and openai_section.get(alias):
                        return str(openai_section.get(alias) or '').strip()
    except Exception:
        pass

    return ''


def _masked_key(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if len(text) <= 12:
        return text[:3] + '...' + text[-2:]
    return text[:7] + '...' + text[-4:]


def ai_enabled() -> bool:
    return bool(_secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key'))


def _model_name() -> str:
    return _secret_value('OPENAI_MODEL', 'openai_model', 'model') or DEFAULT_MODEL


def validate_openai_connection() -> dict[str, str | bool]:
    """Valida se a chave OpenAI existe e se a API responde sem revelar a chave."""
    api_key = _secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key')
    model = _model_name()

    if not api_key:
        return {
            'ok': False,
            'status': 'CHAVE NÃO ENCONTRADA',
            'model': model,
            'key': '',
            'message': 'Configure OPENAI_API_KEY ou [openai].api_key nas secrets do Streamlit e salve as alterações.',
        }

    payload = {
        'model': model,
        'temperature': 0,
        'max_tokens': 8,
        'messages': [
            {'role': 'system', 'content': 'Responda apenas OK.'},
            {'role': 'user', 'content': 'Teste de conexão.'},
        ],
    }

    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=20,
        )
        if response.status_code == 401:
            return {
                'ok': False,
                'status': 'CHAVE INVÁLIDA',
                'model': model,
                'key': _masked_key(api_key),
                'message': 'A API recusou a chave. Confira se a secret foi copiada corretamente e começa com sk-.',
            }
        if response.status_code == 429:
            return {
                'ok': False,
                'status': 'LIMITE/CRÉDITO',
                'model': model,
                'key': _masked_key(api_key),
                'message': 'A chave existe, mas a API retornou limite, cota ou crédito insuficiente.',
            }
        response.raise_for_status()
        return {
            'ok': True,
            'status': 'CONECTADO',
            'model': model,
            'key': _masked_key(api_key),
            'message': 'OpenAI respondeu com sucesso. O complemento de IA está pronto para o scraper.',
        }
    except Exception as exc:
        return {
            'ok': False,
            'status': 'ERRO DE CONEXÃO',
            'model': model,
            'key': _masked_key(api_key),
            'message': str(exc),
        }


def _field_schema(contract: Iterable[RequestedField]) -> list[dict[str, str]]:
    return [
        {
            'column': field.original,
            'kind': field.kind,
            'required': 'yes' if field.required else 'no',
        }
        for field in contract
    ]


def _safe_json_loads(text: str) -> dict:
    raw = str(text or '').strip()
    if raw.startswith('```'):
        raw = raw.strip('`')
        raw = raw.replace('json\n', '', 1).replace('JSON\n', '', 1)
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _clean_ai_row(row: dict[str, object], contract: list[RequestedField]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for field in contract:
        value = clean_cell(row.get(field.original, ''))
        if field.kind == 'gtin':
            value = clean_gtin(value)
        if field.kind == 'imagem':
            parts = [clean_cell(part) for part in value.replace('\n', '|').replace(',', '|').split('|')]
            value = '|'.join(dict.fromkeys([part for part in parts if part.startswith(('http://', 'https://'))]))
        if field.kind == 'estoque':
            key = normalize_key(value)
            if any(term in key for term in ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque']):
                value = '0'
        cleaned[field.original] = value
    return cleaned


def enrich_row_with_ai(
    *,
    current_row: dict[str, str],
    contract: list[RequestedField],
    page_url: str,
    page_text: str,
    operation: str,
) -> dict[str, str]:
    """Usa OpenAI como complemento opcional para preencher somente colunas solicitadas.

    Se não houver chave configurada, ou se a API falhar, retorna a linha original sem quebrar o scraper.
    """
    if not contract or not ai_enabled():
        return current_row

    missing = [field.original for field in contract if not str(current_row.get(field.original, '')).strip()]
    if not missing:
        return current_row

    api_key = _secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key')
    if not api_key:
        return current_row

    context = clean_cell(page_text)[:MAX_CONTEXT_CHARS]
    if not context:
        return current_row

    system = (
        'Você é um assistente de extração de dados para importação no Bling. '
        'Extraia somente os campos solicitados. Se não encontrar um campo com segurança, devolva string vazia. '
        'Não invente valores. Para imagens, use URLs separadas por |. Para sem estoque/indisponível, use 0.'
    )
    user = {
        'operation': operation,
        'url': page_url,
        'requested_fields': _field_schema(contract),
        'current_partial_row': current_row,
        'missing_columns': missing,
        'page_text': context,
        'output_rule': 'Responda apenas JSON com uma chave row contendo exatamente as colunas solicitadas.',
    }

    payload = {
        'model': _model_name(),
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)},
        ],
    }

    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content']
        parsed = _safe_json_loads(content)
        ai_row = parsed.get('row', parsed)
        if not isinstance(ai_row, dict):
            return current_row
        cleaned = _clean_ai_row(ai_row, contract)
        merged = dict(current_row)
        for field in contract:
            if not str(merged.get(field.original, '')).strip() and str(cleaned.get(field.original, '')).strip():
                merged[field.original] = cleaned[field.original]
        return merged
    except Exception:
        return current_row
