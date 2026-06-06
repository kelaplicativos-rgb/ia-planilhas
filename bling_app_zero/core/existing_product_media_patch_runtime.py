from __future__ import annotations

from typing import Any

import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.product_persistence_check import product_persistence_flags

RESPONSIBLE_FILE = 'bling_app_zero/core/existing_product_media_patch_runtime.py'
_INSTALLED = False


def _links(payload: dict[str, Any]) -> list[str]:
    midia = payload.get('midia') if isinstance(payload.get('midia'), dict) else {}
    imagens = midia.get('imagens') if isinstance(midia.get('imagens'), (list, dict)) else payload.get('imagens') or payload.get('images') or []
    raw = []
    if isinstance(imagens, dict):
        raw = imagens.get('imagensURL') or imagens.get('externas') or imagens.get('links') or imagens.get('urls') or []
    elif isinstance(imagens, list):
        raw = imagens
    out: list[str] = []
    for item in raw:
        value = str((item.get('link') or item.get('url')) if isinstance(item, dict) else item or '').strip()
        if value.startswith(('http://', 'https://')) and value not in out:
            out.append(value)
    return out[:3]


def _has_image(saved: dict[str, Any]) -> bool:
    return bool(product_persistence_flags(saved or {}).get('imagens'))


def _payloads(url: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        ('produto.midia.imagensURL.link', {'midia': {'imagens': {'imagensURL': [{'link': url}]}}}),
        ('produto.midia.imagensURL.url', {'midia': {'imagens': {'imagensURL': [{'url': url}]}}}),
        ('produto.midia.externas.link', {'midia': {'imagens': {'externas': [{'link': url}]}}}),
        ('produto.midia.imagens.list', {'midia': {'imagens': [{'link': url}]}}),
    ]


def install_existing_product_media_patch_runtime() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        from bling_app_zero.core import bling_product_image_client as module
        original = getattr(module, '_existing_media_original_push_product_images', None)
        if original is None:
            original = module.push_product_images
            setattr(module, '_existing_media_original_push_product_images', original)

        def push_product_images_existing_first(*, product_id: str, payload: dict[str, Any], url_builder, headers: dict[str, str], get_product):
            attempts: list[dict[str, Any]] = []
            links = _links(payload)
            before = get_product(str(product_id)) if product_id else {}
            if product_id and links and not _has_image(before):
                for image_url in links:
                    for label, media_payload in _payloads(image_url):
                        try:
                            response = requests.patch(url_builder(f'/produtos/{product_id}'), headers=headers, json=media_payload, timeout=12)
                            attempts.append({'mode': 'existing_product_media_patch', 'method': 'PATCH', 'path': f'/produtos/{product_id}', 'label': label, 'status': int(response.status_code), 'response_preview': str(response.text or '')[:500]})
                        except Exception as exc:
                            attempts.append({'mode': 'existing_product_media_patch', 'method': 'PATCH', 'path': f'/produtos/{product_id}', 'label': label, 'status': 'EXCEPTION', 'error': str(exc)[:220]})
                        saved = get_product(str(product_id))
                        if _has_image(saved):
                            add_audit_event('existing_product_media_patch_persisted', area='BLING_IMAGEM', status='OK', details={'product_id': str(product_id), 'image_url': image_url, 'attempts': attempts[-8:], 'responsible_file': RESPONSIBLE_FILE})
                            return True, attempts
                add_audit_event('existing_product_media_patch_not_persisted', area='BLING_IMAGEM', status='AVISO', details={'product_id': str(product_id), 'links': links, 'attempts': attempts[-8:], 'responsible_file': RESPONSIBLE_FILE})
            ok, more_attempts = original(product_id=product_id, payload=payload, url_builder=url_builder, headers=headers, get_product=get_product)
            return ok, attempts + list(more_attempts or [])

        module.push_product_images = push_product_images_existing_first
        _INSTALLED = True
        add_audit_event('existing_product_media_patch_runtime_installed', area='BLING_IMAGEM', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
        return True
    except Exception as exc:
        _INSTALLED = True
        add_audit_event('existing_product_media_patch_runtime_install_failed', area='BLING_IMAGEM', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False


__all__ = ['install_existing_product_media_patch_runtime']
