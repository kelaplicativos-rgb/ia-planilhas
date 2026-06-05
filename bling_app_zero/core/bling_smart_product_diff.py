from __future__ import annotations

import re
from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_smart_product_diff.py'

_IMAGE_VARIANT_RE = re.compile(
    r'(?:[-_](?:\d{2,5}x\d{2,5}|\d{2,5}w|\d{2,5}h|small|medium|large|thumb|thumbnail|scaled|resize|resized|original|webp|jpg|jpeg|png|avif))*$',
    re.IGNORECASE,
)
_IMAGE_HASH_RE = re.compile(r'[-_][a-f0-9]{8,32}$', re.IGNORECASE)


def _extract_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in ('data', 'dados', 'result'):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested
        return payload
    return {}


def _clean_text(value: Any) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _cmp_text(value: Any) -> str:
    return _clean_text(value).lower()


def _cmp_number(value: Any) -> str:
    text = str(value or '').strip().replace('R$', '').replace(' ', '')
    if not text:
        return ''
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    try:
        return f'{float(text):.4f}'
    except Exception:
        return _cmp_text(value)


def _dig(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return ''
        current = current.get(key)
    return current


def _image_key(value: Any) -> str:
    text = str(value or '').strip().lower().replace('\\', '/')
    if not text:
        return ''
    text = text.split('?', 1)[0].split('#', 1)[0]
    text = text.rstrip('/').rsplit('/', 1)[-1]
    text = re.sub(r'\.(?:jpg|jpeg|png|webp|gif|bmp|tif|tiff|avif)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'@\d+x$', '', text, flags=re.IGNORECASE)
    text = _IMAGE_VARIANT_RE.sub('', text)
    text = _IMAGE_HASH_RE.sub('', text)
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text


def _cmp_images(value: Any) -> str:
    keys: list[str] = []
    for item in _images_from_any(value):
        key = _image_key(item)
        if key and key not in keys:
            keys.append(key)
    return '|'.join(sorted(keys))


def _images_from_any(value: Any) -> list[str]:
    images: list[str] = []
    if isinstance(value, dict):
        for key in ('midia', 'media'):
            images.extend(_images_from_any(value.get(key)))
        for key in ('imagens', 'images', 'imagem', 'image'):
            images.extend(_images_from_any(value.get(key)))
        for key in ('link', 'url', 'src', 'href'):
            item = value.get(key)
            if item:
                images.append(str(item))
    elif isinstance(value, list):
        for item in value:
            images.extend(_images_from_any(item))
    elif isinstance(value, str):
        for part in re.split(r'[|;,]\s*', value):
            if part.strip():
                images.append(part.strip())
    clean: list[str] = []
    for item in images:
        text = str(item or '').strip()
        if text and text not in clean:
            clean.append(text)
    return clean


def _existing_comparable(existing: dict[str, Any]) -> dict[str, str]:
    tributacao = existing.get('tributacao') if isinstance(existing.get('tributacao'), dict) else {}
    categoria = existing.get('categoria') if isinstance(existing.get('categoria'), dict) else {}
    return {
        'nome': _cmp_text(existing.get('nome') or existing.get('descricao')),
        'codigo': _cmp_text(existing.get('codigo') or existing.get('sku')),
        'preco': _cmp_number(existing.get('preco') or existing.get('precoVenda')),
        'descricaoCurta': _cmp_text(existing.get('descricaoCurta') or existing.get('descricao') or existing.get('descricaoComplementar')),
        'marca': _cmp_text(existing.get('marca')),
        'unidade': _cmp_text(existing.get('unidade')),
        'formato': _cmp_text(existing.get('formato')),
        'situacao': _cmp_text(existing.get('situacao')),
        'ncm': _cmp_text(tributacao.get('ncm') or existing.get('ncm')),
        'categoria_id': _cmp_text(categoria.get('id') or existing.get('idCategoria')),
        'categoria_descricao': _cmp_text(categoria.get('descricao') or categoria.get('nome') or existing.get('categoria')),
        'imagens': _cmp_images(existing.get('midia') or existing.get('imagens') or existing.get('images')),
    }


def _payload_comparable(payload: dict[str, Any]) -> dict[str, str]:
    tributacao = payload.get('tributacao') if isinstance(payload.get('tributacao'), dict) else {}
    categoria = payload.get('categoria') if isinstance(payload.get('categoria'), dict) else {}
    return {
        'nome': _cmp_text(payload.get('nome')),
        'codigo': _cmp_text(payload.get('codigo')),
        'preco': _cmp_number(payload.get('preco')),
        'descricaoCurta': _cmp_text(payload.get('descricaoCurta')),
        'marca': _cmp_text(payload.get('marca')),
        'unidade': _cmp_text(payload.get('unidade')),
        'formato': _cmp_text(payload.get('formato')),
        'situacao': _cmp_text(payload.get('situacao')),
        'ncm': _cmp_text(tributacao.get('ncm')),
        'categoria_id': _cmp_text(categoria.get('id')),
        'categoria_descricao': _cmp_text(categoria.get('descricao') or categoria.get('nome')),
        'imagens': _cmp_images(payload.get('midia') or payload.get('imagens') or payload.get('images')),
    }


def _changed_fields(existing: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    old = _existing_comparable(existing)
    new = _payload_comparable(payload)
    changed: list[str] = []
    for field, new_value in new.items():
        if not new_value:
            continue
        old_value = old.get(field, '')
        if old_value != new_value:
            changed.append(field)
    return changed


def fetch_existing_product_detail(
    *,
    token: dict[str, Any],
    product_id: str,
    url_builder: Callable[[str], str],
    headers_builder: Callable[[dict[str, Any]], dict[str, str]],
    timeout: int,
) -> dict[str, Any]:
    try:
        response = requests.get(url_builder(f'/produtos/{product_id}'), headers=headers_builder(token), timeout=timeout)
        if response.status_code >= 400:
            return {}
        return _extract_dict(response.json())
    except Exception:
        return {}


def update_existing_product_if_changed(
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
    existing = fetch_existing_product_detail(
        token=token,
        product_id=product_id,
        url_builder=url_builder,
        headers_builder=headers_builder,
        timeout=timeout,
    )

    for strategy, payload, meta in variants:
        update_payload = dict(payload)
        changed = _changed_fields(existing, update_payload) if existing else list(update_payload.keys())
        if existing and not changed:
            attempts.append({
                'mode': 'skip_unchanged',
                'product_id': product_id,
                'strategy': strategy,
                'status': 'UNCHANGED',
                'confidence': meta.get('confidence'),
                'changed_fields': [],
            })
            add_audit_event(
                'bling_smart_product_unchanged_skipped',
                area='BLING_ENVIO',
                status='PULADO',
                details={'product_id': product_id, 'strategy': strategy, 'responsible_file': responsible_file},
            )
            return 'unchanged', attempts

        for method in ('PUT', 'PATCH'):
            try:
                response = requests.request(
                    method,
                    url_builder(f'/produtos/{product_id}'),
                    headers=headers_builder(token),
                    json=update_payload,
                    timeout=timeout,
                )
                attempts.append({
                    'mode': 'update_existing',
                    'method': method,
                    'product_id': product_id,
                    'strategy': strategy,
                    'status': int(response.status_code),
                    'confidence': meta.get('confidence'),
                    'changed_fields': changed,
                    'response_preview': str(response.text or '')[:300],
                })
                if response.status_code < 400:
                    add_audit_event(
                        'bling_smart_product_changed_updated',
                        area='BLING_ENVIO',
                        status='OK',
                        details={
                            'product_id': product_id,
                            'strategy': strategy,
                            'changed_fields': changed,
                            'responsible_file': responsible_file,
                        },
                    )
                    return 'updated', attempts
                if response.status_code in {401, 403, 404}:
                    break
            except Exception as exc:
                attempts.append({
                    'mode': 'update_existing',
                    'method': method,
                    'product_id': product_id,
                    'strategy': strategy,
                    'status': 'EXCEPTION',
                    'changed_fields': changed,
                    'error': str(exc)[:240],
                })
    return 'failed', attempts


__all__ = ['fetch_existing_product_detail', 'update_existing_product_if_changed']
