from __future__ import annotations

import json
from typing import Any

import httpx

from bling_app_zero.ai.ai_cache import cache_get, cache_set, make_cache_key
from bling_app_zero.ai.ai_config import AISettings, get_ai_settings
from bling_app_zero.ai.ai_schema import AIResult

OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
REQUEST_TIMEOUT_SECONDS = 45.0


class AIClientError(RuntimeError):
    pass


def _redact_key(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if len(text) <= 10:
        return '***'
    return f'{text[:4]}...{text[-4:]}'


def _headers(api_key: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _extract_text(response_json: dict[str, Any]) -> str:
    if not isinstance(response_json, dict):
        return ''
    output_text = response_json.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: list[str] = []
    for item in response_json.get('output', []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content', []) or []:
            if not isinstance(content, dict):
                continue
            if isinstance(content.get('text'), str):
                texts.append(content['text'])
    return '\n'.join(texts).strip()


def _strip_code_fence(text: str) -> str:
    cleaned = str(text or '').strip()
    if not cleaned.startswith('```'):
        return cleaned
    cleaned = cleaned.strip('`').strip()
    if cleaned.lower().startswith('json'):
        cleaned = cleaned[4:].strip()
    return cleaned


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text)
    if not cleaned:
        return {}
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return {'text': text}
    return parsed if isinstance(parsed, dict) else {'items': parsed}


def validate_openai_key(api_key: str | None = None) -> AIResult:
    settings = get_ai_settings()
    key = str(api_key or settings.api_key or '').strip()
    if not key:
        return AIResult(ok=False, task='validate_key', message='Informe sua chave OpenAI para ativar a IA.', error='missing_api_key')
    if not key.startswith('sk-'):
        return AIResult(ok=False, task='validate_key', message='A chave informada não parece uma chave OpenAI válida.', error='invalid_prefix')
    return AIResult(ok=True, task='validate_key', message='Chave carregada na sessão.', data={'key_preview': _redact_key(key), 'model': settings.model})


def call_openai_json(task: str, instructions: str, payload: dict[str, Any], *, settings: AISettings | None = None) -> AIResult:
    current = settings or get_ai_settings()
    if not current.ready:
        return AIResult(ok=False, task=task, message=current.status, error='ai_not_ready')

    cache_key = make_cache_key(task, payload, model=current.model)
    cached = cache_get(cache_key)
    if isinstance(cached, AIResult):
        return cached
    if isinstance(cached, dict):
        return AIResult(ok=True, task=task, data=cached, message='Resultado recuperado do cache.')

    safe_instructions = (
        instructions.strip()
        + '\n\nResponda exclusivamente em JSON válido. Não use markdown, comentários ou texto fora do JSON.'
    )
    request_payload = {
        'model': current.model,
        'input': [
            {
                'role': 'system',
                'content': safe_instructions,
            },
            {
                'role': 'user',
                'content': json.dumps(payload, ensure_ascii=False, default=str),
            },
        ],
        'text': {'format': {'type': 'json_object'}},
        'temperature': 0,
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(OPENAI_RESPONSES_URL, headers=_headers(current.api_key), json=request_payload)
        if response.status_code >= 400:
            return AIResult(
                ok=False,
                task=task,
                message='A OpenAI recusou a solicitação. Confira a chave e o saldo da conta.',
                error=f'http_{response.status_code}',
                data={'status_code': response.status_code, 'body': response.text[:500]},
            )
        response_json = response.json()
        text = _extract_text(response_json)
        data = _parse_json_text(text)
        result = AIResult(ok=True, task=task, data=data, message='IA concluiu a análise.')
        cache_set(cache_key, result)
        return result
    except Exception as exc:
        return AIResult(ok=False, task=task, message='Falha ao chamar a IA.', error=str(exc))


__all__ = ['AIClientError', 'OPENAI_RESPONSES_URL', 'call_openai_json', 'validate_openai_key']
