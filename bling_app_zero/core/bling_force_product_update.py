from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_force_product_update.py'
DEFAULT_PESO = 0.300
DEFAULT_LARGURA = 11
DEFAULT_ALTURA = 2
DEFAULT_PROFUNDIDADE = 16
DEFAULT_VOLUMES = 1
DEFAULT_ITENS_CAIXA = 1


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


def _augment_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload)
    nome = str(out.get('nome') or '').strip()
    if nome and not str(out.get('descricaoCurta') or '').strip():
        out['descricaoCurta'] = nome
    if nome and not str(out.get('descricaoComplementar') or '').strip():
        out['descricaoComplementar'] = str(out.get('descricaoCurta') or nome)
    out.setdefault('tipo', 'P')
    out.setdefault('situacao', 'A')
    out.setdefault('formato', 'S')
    out.setdefault('unidade', 'UN')
    out.setdefault('pesoLiquido', DEFAULT_PESO)
    out.setdefault('pesoBruto', DEFAULT_PESO)
    out.setdefault('volumes', DEFAULT_VOLUMES)
    out.setdefault('itensPorCaixa', DEFAULT_ITENS_CAIXA)
    dimensoes = out.get('dimensoes') if isinstance(out.get('dimensoes'), dict) else {}
    dimensoes.setdefault('largura', DEFAULT_LARGURA)
    dimensoes.setdefault('altura', DEFAULT_ALTURA)
    dimensoes.setdefault('profundidade', DEFAULT_PROFUNDIDADE)
    out['dimensoes'] = dimensoes
    return _clean(out)


def _without_media(payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload)
    out.pop('midia', None)
    out.pop('imagens', None)
    out.pop('images', None)
    return _clean(out)


def _minimal(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ('nome', 'codigo', 'preco', 'descricaoCurta', 'descricaoComplementar', 'marca', 'unidade', 'tipo', 'situacao', 'formato', 'pesoLiquido', 'pesoBruto', 'volumes', 'itensPorCaixa'):
        if payload.get(key) not in ('', None, {}, []):
            out[key] = payload[key]
    for key in ('tributacao', 'categoria', 'dimensoes'):
        if isinstance(payload.get(key), dict):
            out[key] = _clean(payload[key])
    return _clean(out)


def _image_links(payload: dict[str, Any]) -> list[str]:
    midia = payload.get('midia') if isinstance(payload.get('midia'), dict) else {}
    imagens = midia.get('imagens') if isinstance(midia.get('imagens'), (list, dict)) else payload.get('imagens') or payload.get('images') or []
    raw: list[Any]
    if isinstance(imagens, dict):
        raw = list(imagens.get('externas') or imagens.get('externos') or imagens.get('links') or imagens.get('urls') or [])
    elif isinstance(imagens, list):
        raw = imagens
    else:
        raw = []
    links: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            link = str(item.get('link') or item.get('url') or item.get('URL') or '').strip()
        else:
            link = str(item or '').strip()
        if link.startswith(('http://', 'https://')) and link not in links:
            links.append(link)
    return links[:10]


def _media_variants(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    links = _image_links(payload)
    if not links:
        return []
    by_link = [{'link': link} for link in links]
    by_url = [{'url': link} for link in links]
    by_both = [{'link': link, 'url': link} for link in links]
    return [
        ('midia_imagens_lista_link', {'midia': {'imagens': by_link}}),
        ('midia_imagens_lista_url', {'midia': {'imagens': by_url}}),
        ('midia_imagens_lista_link_url', {'midia': {'imagens': by_both}}),
        ('midia_imagens_externas_link', {'midia': {'imagens': {'externas': by_link}}}),
        ('midia_imagens_externas_url', {'midia': {'imagens': {'externas': by_url}}}),
        ('midia_imagens_externos_link', {'midia': {'imagens': {'externos': by_link}}}),
        ('midia_imagens_externos_url', {'midia': {'imagens': {'externos': by_url}}}),
        ('imagens_raiz_link', {'imagens': by_link}),
        ('imagens_raiz_url', {'imagens': by_url}),
    ]


def _description_variants(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    value = str(payload.get('descricaoCurta') or payload.get('descricao') or payload.get('nome') or '').strip()
    if not value:
        return []
    return [
        ('descricao_curta', {'descricaoCurta': value}),
        ('descricao_complementar', {'descricaoComplementar': value}),
        ('descricao_dupla', {'descricaoCurta': value, 'descricaoComplementar': value}),
    ]


def _post_success_reinforcement(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    out.extend(_media_variants(payload))
    out.extend(_description_variants(payload))
    return [(label, _clean(item)) for label, item in out if _clean(item)]


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
    if isinstance(payload.get('dimensoes'), dict):
        for key in payload['dimensoes'].keys():
            names.add(f'dimensoes_{key}')
    return sorted(str(item) for item in names)


def _payload_options(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    full = _augment_defaults(_clean(deepcopy(payload)))
    options = [
        ('todos_os_campos_com_defaults', full),
        ('sem_midia_com_defaults', _without_media(full)),
        ('minimo_com_defaults', _minimal(full)),
    ]
    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for label, item in options:
        marker = repr(sorted(item.items()))
        if item and marker not in seen:
            out.append((label, item))
            seen.add(marker)
    return out


def _extract_saved_product(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ('data', 'dados', 'produto', 'result'):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _fetch_persisted(*, endpoint: str, headers: dict[str, str], timeout: int, product_id: str) -> dict[str, Any]:
    try:
        response = requests.get(endpoint, headers=headers, timeout=timeout)
        data = response.json() if str(response.text or '').strip() else {}
        saved = _extract_saved_product(data)
        add_audit_event(
            'bling_product_persistence_checked',
            area='BLING_ENVIO',
            status='OK' if response.status_code < 400 else 'AVISO',
            details={
                'product_id': product_id,
                'status': int(response.status_code),
                'saved_keys': sorted(saved.keys()) if isinstance(saved, dict) else [],
                'has_descricao_curta': bool(isinstance(saved, dict) and saved.get('descricaoCurta')),
                'has_descricao_complementar': bool(isinstance(saved, dict) and saved.get('descricaoComplementar')),
                'has_midia': bool(isinstance(saved, dict) and saved.get('midia')),
                'has_imagens': bool(isinstance(saved, dict) and (saved.get('imagens') or (isinstance(saved.get('midia'), dict) and saved.get('midia', {}).get('imagens')))),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return saved if isinstance(saved, dict) else {}
    except Exception as exc:
        add_audit_event(
            'bling_product_persistence_check_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'product_id': product_id, 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return {}


def _reinforce_after_success(*, endpoint: str, headers: dict[str, str], payload: dict[str, Any], timeout: int, attempts: list[dict[str, Any]], product_id: str) -> None:
    for label, patch_payload in _post_success_reinforcement(payload):
        try:
            response = requests.patch(endpoint, headers=headers, json=patch_payload, timeout=timeout)
            attempts.append({
                'mode': 'post_success_reinforcement',
                'method': 'PATCH',
                'product_id': product_id,
                'payload_label': label,
                'status': int(response.status_code),
                'payload_keys': sorted(patch_payload.keys()),
                'changed_fields': _fields(patch_payload),
                'response_preview': str(response.text or '')[:500],
            })
            if response.status_code < 400:
                add_audit_event(
                    'bling_product_post_success_reinforcement_ok',
                    area='BLING_ENVIO',
                    status='OK',
                    details={'product_id': product_id, 'payload_label': label, 'payload_keys': sorted(patch_payload.keys()), 'fields': _fields(patch_payload), 'responsible_file': RESPONSIBLE_FILE},
                )
        except Exception as exc:
            attempts.append({'mode': 'post_success_reinforcement', 'method': 'PATCH', 'product_id': product_id, 'payload_label': label, 'status': 'EXCEPTION', 'error': str(exc)[:240]})


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
            methods = ('PUT', 'PATCH') if label.startswith('todos_os_campos') else ('PATCH', 'PUT')
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
                        _reinforce_after_success(endpoint=endpoint, headers=headers, payload=update_payload, timeout=timeout, attempts=attempts, product_id=product_id)
                        _fetch_persisted(endpoint=endpoint, headers=headers, timeout=timeout, product_id=product_id)
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
                                'post_success_reinforcement': True,
                                'persistence_check': True,
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
