from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_force_product_update.py'


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).startswith('_'):
                continue
            cleaned = _clean(item)
            if cleaned not in ('', None, {}, []):
                out[key] = cleaned
        return out
    if isinstance(value, list):
        return [item for item in (_clean(item) for item in value) if item not in ('', None, {}, [])]
    return value


def _without_media(payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload)
    out.pop('midia', None)
    out.pop('imagens', None)
    out.pop('images', None)
    return _clean(out)


def _minimal(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ('nome', 'codigo', 'preco', 'descricaoCurta', 'marca', 'unidade', 'tipo', 'situacao', 'formato'):
        if payload.get(key) not in ('', None, {}, []):
            out[key] = payload[key]
    for key in ('tributacao', 'categoria'):
        if isinstance(payload.get(key), dict):
            out[key] = _clean(payload[key])
    return _clean(out)


def _fields(payload: dict[str, Any]) -> list[str]:
    names: set[str] = set(payload.keys())
    if 'midia' in payload:
        names.add('imagens')
    if isinstance(payload.get('tributacao'), dict):
        for key in payload['tributacao'].keys():
            names.add(f'tributacao_{key}')
    if isinstance(payload.get('categoria'), dict):
        for key in payload['categoria'].keys():
            names.add(f'categoria_{key}')
    return sorted(str(item) for item in names)


def _payload_options(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    full = _clean(deepcopy(payload))
    options = [
        ('todos_os_campos', full),
        ('sem_midia', _without_media(full)),
        ('minimo', _minimal(full)),
    ]
    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for label, item in options:
        marker = repr(sorted(item.items()))
        if item and marker not in seen:
            out.append((label, item))
            seen.add(marker)
    return out


def update_existing_product_complete(
    *,
    token: dict[str, Any],
    product_id: str,
    variants: list[tuple[str, dict[str, Any], dict[str, Any]]],
    url_builder: Callable[[str], str],
    headers_builder: Callable[[dict[str, Any]], dict[str, str]],
    timeout: int,
    responsible_file: str,
) -> tuple[str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    endpoint = url_builder(f'/produtos/{product_id}')
    headers = headers_builder(token)

    for strategy, payload, meta in variants:
        for label, update_payload in _payload_options(payload):
            methods = ('PUT', 'PATCH') if label == 'todos_os_campos' else ('PATCH', 'PUT')
            for method in methods:
                try:
                    response = requests.request(method, endpoint, headers=headers, json=update_payload, timeout=timeout)
                    item = {
                        'mode': 'complete_update_existing',
                        'method': method,
                        'product_id': product_id,
                        'strategy': strategy,
                        'payload_label': label,
                        'status': int(response.status_code),
                        'confidence': meta.get('confidence'),
                        'changed_fields': _fields(update_payload),
                        'payload_keys': sorted(update_payload.keys()),
                        'response_preview': str(response.text or '')[:500],
                    }
                    attempts.append(item)
                    if response.status_code < 400:
                        add_audit_event(
                            'bling_product_complete_updated',
                            area='BLING_ENVIO',
                            status='OK',
                            details={
                                'product_id': product_id,
                                'method': method,
                                'strategy': strategy,
                                'payload_label': label,
                                'payload_keys': item['payload_keys'],
                                'fields': item['changed_fields'],
                                'responsible_file': responsible_file,
                            },
                        )
                        return 'updated', attempts
                    if response.status_code in {401, 403, 404}:
                        break
                except Exception as exc:
                    attempts.append({
                        'mode': 'complete_update_existing',
                        'method': method,
                        'product_id': product_id,
                        'strategy': strategy,
                        'payload_label': label,
                        'status': 'EXCEPTION',
                        'changed_fields': _fields(update_payload),
                        'payload_keys': sorted(update_payload.keys()),
                        'error': str(exc)[:240],
                    })

    add_audit_event(
        'bling_product_complete_update_failed',
        area='BLING_ENVIO',
        status='ERRO',
        details={'product_id': product_id, 'attempts': attempts[-8:], 'responsible_file': responsible_file},
    )
    return 'failed', attempts


__all__ = ['update_existing_product_complete']
