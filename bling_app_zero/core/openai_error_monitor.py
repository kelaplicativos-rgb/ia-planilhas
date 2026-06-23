from __future__ import annotations

import json
import os
import re
import traceback
from collections.abc import MutableMapping
from datetime import datetime
from typing import Any

import httpx

from bling_app_zero.core.app_config import APP_VERSION
from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.debug import add_debug, get_debug_logs

RESPONSIBLE_FILE = 'bling_app_zero/core/openai_error_monitor.py'
DIAGNOSTIC_RESULT_KEY = 'openai_error_monitor_last_result_v1'
DIAGNOSTIC_CONTEXT_KEY = 'openai_error_monitor_last_context_v1'
DIAGNOSTIC_MODEL_KEY = 'openai_error_monitor_model_v1'
DEFAULT_MODEL = 'gpt-5.4-mini'
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
MAX_PAYLOAD_CHARS = 22000
MAX_EVENT_ITEMS = 120
REDACTED = '[REDACTED]'
BOOT_EVENTS_KEY = 'mapeiaai_boot_diagnostic_events_v1'
BOOT_UPLOADS_KEY = 'mapeiaai_boot_uploads_v1'
BOOT_MODEL_META_KEY = 'mapeiaai_boot_model_upload_last_meta_v1'

SENSITIVE_PATTERNS = (
    re.compile(r'sk-[A-Za-z0-9_\-]{12,}'),
    re.compile(r'Bearer\s+[A-Za-z0-9_\.\-]+', re.IGNORECASE),
    re.compile(r'(?i)(api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|cookie|senha|password)\s*[:=]\s*([^\s,;]+)'),
)

SENSITIVE_KEYWORDS = (
    'api_key',
    'apikey',
    'client_secret',
    'secret',
    'token',
    'authorization',
    'cookie',
    'senha',
    'password',
    'credential',
    'credentials',
    'refresh',
    'access_token',
)

ERROR_WORDS = ('erro', 'error', 'exception', 'traceback', 'falha', 'failed', 'invalid', 'unauthorized', 'timeout', 'bloqueado', 'blocked', 'gate')
IMPORTANT_STATE_KEYS = (
    'app_mode',
    'selected_home_action',
    'home_route',
    'bling_wizard_step',
    'home_wizard_step',
    'home_active_operation_v2',
    'mapear_planilha_sem_api_active',
    'mapeiaai_flow_kind',
    'flow_kind',
    'operation',
    'operation_type',
    'origem_dados',
    'source_type',
    'send_mode',
    'api_site_send_mode',
    'api_site_batch_contract',
    'price_api_skip_predeep_discovery',
    'unified_api_site_engine',
    'site_capture_running',
    'site_capture_rows',
    'site_capture_error',
    'site_capture_last_url',
    'mapeiaai_universal_model_upload',
    'mapeiaai_universal_model_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'mapeiaai_universal_source_df',
    BOOT_EVENTS_KEY,
    BOOT_UPLOADS_KEY,
    BOOT_MODEL_META_KEY,
    'df_final_cadastro_preview_rules_applied',
    'df_final',
    'mapped_df',
)


def _streamlit_module() -> Any | None:
    try:
        import streamlit as st

        return st
    except Exception:
        return None


def _state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return {}


def _redact_text(value: Any, limit: int = 1200) -> str:
    text = str(value or '').replace('\x00', '').strip()
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(lambda match: f'{match.group(1)}={REDACTED}' if match.lastindex and match.lastindex >= 1 else REDACTED, text)
    if len(text) > limit:
        text = text[:limit] + '...'
    return text


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _summarize_value(value: Any, *, key: str = '', depth: int = 0) -> Any:
    """Sanitiza preservando diagnóstico útil.

    BLINGFIX 2026-06-23: o diagnóstico antigo retornava apenas "str" e "dict"
    dentro de audit_events_relevantes, apagando exatamente a causa do erro. A
    profundidade foi ampliada e UploadedFile/DataFrame recebem resumo seguro,
    sem expor conteúdo da planilha nem credenciais.
    """
    if _is_sensitive_key(key):
        return REDACTED
    if depth > 6:
        return _redact_text(type(value).__name__, 120)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_text(value, 900)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value or b'')
        return {'type': 'bytes', 'size': len(raw)}
    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            return {
                'type': type(value).__name__,
                'shape': tuple(value.shape),
                'columns': [_redact_text(col, 100) for col in list(value.columns)[:80]],
                'sample_rows': min(int(getattr(value, 'shape', [0])[0] or 0), 3),
            }
        except Exception:
            return {'type': type(value).__name__}
    if hasattr(value, 'name') and (hasattr(value, 'size') or hasattr(value, 'getvalue')):
        try:
            size = getattr(value, 'size', None)
            if size is None:
                data = value.getvalue()
                size = len(data or b'')
        except Exception:
            size = None
        return {
            'type': type(value).__name__,
            'name': _redact_text(getattr(value, 'name', ''), 240),
            'size': size,
            'mime': _redact_text(getattr(value, 'type', ''), 160),
        }
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for sub_key, item in list(value.items())[:80]:
            safe_key = _redact_text(sub_key, 140)
            result[safe_key] = _summarize_value(item, key=str(sub_key), depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_summarize_value(item, depth=depth + 1) for item in list(value)[:80]]
    return {'type': type(value).__name__, 'repr': _redact_text(value, 240)}


def _safe_event(item: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in item.items():
        safe[str(key)] = _summarize_value(value, key=str(key))
    return safe


def _extract_relevant_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    selected: list[dict[str, Any]] = []
    for item in events[-MAX_EVENT_ITEMS:]:
        text = json.dumps(item, ensure_ascii=False, default=str).lower()
        if any(word in text for word in ERROR_WORDS) or 'bootdiag_' in text or 'modelo_upload' in text:
            selected.append(_safe_event(item))
    tail = [_safe_event(item) for item in events[-35:]]
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in selected + tail:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(item)
    return merged[-MAX_EVENT_ITEMS:]


def _collect_state_summary(state: MutableMapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in IMPORTANT_STATE_KEYS:
        if key in state:
            summary[key] = _summarize_value(state.get(key), key=key)
    dataframes: dict[str, Any] = {}
    for key, value in list(state.items()):
        if hasattr(value, 'shape') and hasattr(value, 'columns'):
            dataframes[str(key)] = _summarize_value(value, key=str(key))
    if dataframes:
        summary['dataframes_detectados'] = dataframes
    return summary


def _collect_boot_events(state: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    raw = state.get(BOOT_EVENTS_KEY, [])
    if not isinstance(raw, list):
        return []
    events = [item for item in raw if isinstance(item, dict)]
    return _extract_relevant_events(events)


def get_openai_api_key() -> str:
    env_key = os.getenv('OPENAI_API_KEY') or os.getenv('MAPEIAAI_OPENAI_API_KEY')
    if env_key:
        return str(env_key).strip()
    st = _streamlit_module()
    if st is None:
        return ''
    try:
        secrets = st.secrets
        for key in ('OPENAI_API_KEY', 'openai_api_key'):
            value = secrets.get(key) if hasattr(secrets, 'get') else None
            if value:
                return str(value).strip()
        openai_section = secrets.get('openai') if hasattr(secrets, 'get') else None
        if openai_section:
            value = openai_section.get('api_key') or openai_section.get('OPENAI_API_KEY')
            if value:
                return str(value).strip()
    except Exception:
        return ''
    return ''


def get_diagnostic_model(state: MutableMapping[str, Any] | None = None) -> str:
    store = _state_store(state)
    selected = str(store.get(DIAGNOSTIC_MODEL_KEY) or '').strip()
    if selected:
        return selected
    env_model = os.getenv('OPENAI_DIAGNOSTIC_MODEL') or os.getenv('MAPEIAAI_OPENAI_DIAGNOSTIC_MODEL')
    if env_model:
        return str(env_model).strip()
    st = _streamlit_module()
    if st is not None:
        try:
            openai_section = st.secrets.get('openai') if hasattr(st.secrets, 'get') else None
            if openai_section and openai_section.get('diagnostic_model'):
                return str(openai_section.get('diagnostic_model')).strip()
        except Exception:
            pass
    return DEFAULT_MODEL


def openai_monitor_config_status(state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        'configured': bool(get_openai_api_key()),
        'model': get_diagnostic_model(state),
        'key_sources': 'OPENAI_API_KEY, MAPEIAAI_OPENAI_API_KEY ou st.secrets["openai"]["api_key"]',
        'endpoint': OPENAI_RESPONSES_URL,
    }


def build_diagnostic_context(*, state: MutableMapping[str, Any] | None = None, reason: str = 'manual') -> dict[str, Any]:
    store = _state_store(state)
    events = get_audit_events(store)
    logs = get_debug_logs(store)
    boot_events = _collect_boot_events(store)
    context = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'app': 'IA Planilhas → Bling / MapeiaAI',
        'app_version': APP_VERSION,
        'reason': reason,
        'state_summary': _collect_state_summary(store),
        'boot_events_relevantes': boot_events,
        'boot_uploads_relevantes': _summarize_value(store.get(BOOT_UPLOADS_KEY, {}), key=BOOT_UPLOADS_KEY),
        'audit_events_relevantes': _extract_relevant_events(events),
        'debug_logs_relevantes': _extract_relevant_events(logs),
        'monitor_config': openai_monitor_config_status(store),
        'orientation': {
            'objetivo': 'Identificar a causa provável do erro no fluxo Bling e sugerir correção de arquivo/função sem expor segredos.',
            'regras': [
                'Nunca enviar produto vazio para API.',
                'API nunca deve receber operação universal.',
                'Fluxo Bling/API deve resolver operação real antes do envio.',
                'Imagens devem ser conferidas até chegar ao payload/API.',
                'Produtos sem categoria podem ir para Produtos não classificados para não quebrar cadastro.',
                'Se houver boot_events_relevantes, priorizar esses eventos porque nasceram antes da Home.',
            ],
        },
    }
    return _summarize_value(context)


def _compact_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if len(text) <= MAX_PAYLOAD_CHARS:
        return text
    return text[:MAX_PAYLOAD_CHARS] + '\n... [contexto truncado com segurança]'


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    if isinstance(response_payload.get('output_text'), str):
        return str(response_payload.get('output_text')).strip()
    parts: list[str] = []
    for item in response_payload.get('output') or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content') or []:
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                parts.append(content.get('text', ''))
    return '\n'.join(part.strip() for part in parts if part).strip()


def analyze_current_session_with_openai(*, state: MutableMapping[str, Any] | None = None, reason: str = 'manual') -> dict[str, Any]:
    store = _state_store(state)
    api_key = get_openai_api_key()
    model = get_diagnostic_model(store)
    context = build_diagnostic_context(state=store, reason=reason)
    store[DIAGNOSTIC_CONTEXT_KEY] = context

    if not api_key:
        result = {
            'ok': False,
            'status': 'missing_api_key',
            'message': 'OPENAI_API_KEY não configurada. Configure a chave nos Secrets do Streamlit ou variável de ambiente.',
            'model': model,
            'context': context,
        }
        store[DIAGNOSTIC_RESULT_KEY] = result
        add_audit_event('openai_error_monitor_missing_api_key', area='OPENAI_DIAGNOSTICO', status='AVISO', details={'model': model, 'responsible_file': RESPONSIBLE_FILE}, state=store)
        return result

    prompt = (
        'Você é o monitor técnico do MapeiaAI/IA Planilhas → Bling. '
        'Analise o diagnóstico sanitizado abaixo e devolva em português: '
        '1) causa provável, 2) arquivo/função suspeita, 3) correção recomendada, '
        '4) risco para o Bling/API, 5) próximo teste manual. '
        'Se faltarem dados, diga exatamente quais dados faltam. Não invente segredos nem tokens.\n\n'
        f'{_compact_payload(context)}'
    )
    payload = {
        'model': model,
        'input': [
            {
                'role': 'developer',
                'content': 'Responda como diagnóstico técnico objetivo para correção de código Streamlit/Python/Bling API. Não exponha credenciais.',
            },
            {'role': 'user', 'content': prompt},
        ],
        'max_output_tokens': 1400,
    }

    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json=payload,
            )
        if response.status_code >= 400:
            result = {
                'ok': False,
                'status': f'openai_http_{response.status_code}',
                'message': _redact_text(response.text, 1200),
                'model': model,
                'context': context,
            }
        else:
            data = response.json()
            result = {
                'ok': True,
                'status': 'ok',
                'message': _redact_text(_extract_response_text(data), 5000) or 'A API respondeu, mas sem texto de diagnóstico.',
                'model': model,
                'context': context,
            }
    except Exception as exc:
        result = {
            'ok': False,
            'status': 'exception',
            'message': _redact_text(''.join(traceback.format_exception_only(type(exc), exc)), 1200),
            'model': model,
            'context': context,
        }

    store[DIAGNOSTIC_RESULT_KEY] = result
    add_debug('Diagnóstico OpenAI executado.', origin='OPENAI_DIAGNOSTICO', level='INFO' if result.get('ok') else 'ERRO', details={'status': result.get('status'), 'model': model}, state=store)
    add_audit_event('openai_error_monitor_analyzed_session', area='OPENAI_DIAGNOSTICO', status='OK' if result.get('ok') else 'ERRO', details={'status': result.get('status'), 'model': model, 'responsible_file': RESPONSIBLE_FILE}, state=store)
    return result


def record_exception_for_openai(exc: Exception, *, area: str = 'APP', state: MutableMapping[str, Any] | None = None) -> None:
    store = _state_store(state)
    add_audit_event(
        'exception_captured_for_openai_monitor',
        area=area,
        status='ERRO',
        details={
            'error_type': type(exc).__name__,
            'error': _redact_text(exc, 500),
            'traceback': _redact_text(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)), 3000),
            'responsible_file': RESPONSIBLE_FILE,
        },
        state=store,
    )


__all__ = [
    'DEFAULT_MODEL',
    'DIAGNOSTIC_CONTEXT_KEY',
    'DIAGNOSTIC_MODEL_KEY',
    'DIAGNOSTIC_RESULT_KEY',
    'analyze_current_session_with_openai',
    'build_diagnostic_context',
    'get_diagnostic_model',
    'get_openai_api_key',
    'openai_monitor_config_status',
    'record_exception_for_openai',
]
