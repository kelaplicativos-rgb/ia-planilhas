from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_product_image_client.py'
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TIMEOUT = 10
REQUEST_TIMEOUT = 8
DEEP_SCAN_ENV = 'BLING_IMAGE_DEEP_SCAN'
FAST_JSON_PATHS = 2
FAST_JSON_PAYLOADS = 4
FAST_MAX_ATTEMPTS = 10


@dataclass(frozen=True)
class ImageProbe:
    url: str
    ok: bool
    mime: str
    filename: str
    content: bytes
    error: str = ''


def _deep_scan_enabled() -> bool:
    return str(os.getenv(DEEP_SCAN_ENV, '')).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}


def _image_links_from_payload(payload: dict[str, Any]) -> list[str]:
    midia = payload.get('midia') if isinstance(payload.get('midia'), dict) else {}
    imagens = midia.get('imagens') if isinstance(midia.get('imagens'), (list, dict)) else payload.get('imagens') or payload.get('images') or []
    raw: list[Any]
    if isinstance(imagens, dict):
        raw = list(
            imagens.get('imagensURL')
            or imagens.get('externas')
            or imagens.get('externos')
            or imagens.get('links')
            or imagens.get('urls')
            or []
        )
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
    return links[:3 if _deep_scan_enabled() else 1]


def _safe_filename(url: str, mime: str) -> str:
    path = urlparse(url).path
    name = os.path.basename(path).split('?')[0].strip() or 'produto'
    if '.' not in name:
        ext = mimetypes.guess_extension(mime or 'image/jpeg') or '.jpg'
        name += ext
    return name[:120]


def _download_image(url: str, headers: dict[str, str]) -> ImageProbe:
    try:
        response = requests.get(
            url,
            timeout=IMAGE_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            },
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return ImageProbe(url, False, '', '', b'', f'HTTP {response.status_code}')
        content = response.content or b''
        if not content:
            return ImageProbe(url, False, '', '', b'', 'imagem vazia')
        if len(content) > MAX_IMAGE_BYTES:
            return ImageProbe(url, False, '', '', b'', f'imagem maior que {MAX_IMAGE_BYTES} bytes')
        mime = str(response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if not mime.startswith('image/'):
            guessed = mimetypes.guess_type(url)[0] or ''
            mime = guessed if guessed.startswith('image/') else 'image/jpeg'
        return ImageProbe(url, True, mime, _safe_filename(url, mime), content, '')
    except Exception as exc:
        return ImageProbe(url, False, '', '', b'', str(exc)[:220])


def _json_payloads(url: str) -> list[tuple[str, dict[str, Any]]]:
    link = {'link': url}
    url_obj = {'url': url}
    both = {'link': url, 'url': url}
    payloads = [
        ('json.imagensURL.url', {'midia': {'imagens': {'imagensURL': [url_obj]}}}),
        ('json.imagensURL.link', {'midia': {'imagens': {'imagensURL': [link]}}}),
        ('json.imagensURL.link_url', {'midia': {'imagens': {'imagensURL': [both]}}}),
        ('json.imagensURL.string', {'midia': {'imagens': {'imagensURL': [url]}}}),
        ('json.externas.url', {'midia': {'imagens': {'externas': [url_obj]}}}),
        ('json.externas.link', {'midia': {'imagens': {'externas': [link]}}}),
        ('json.imagens.list.url', {'midia': {'imagens': [url_obj]}}),
        ('json.root.imagens.url', {'imagens': [url_obj]}),
        ('json.root.imagensURL', {'imagensURL': [url_obj]}),
    ]
    return payloads if _deep_scan_enabled() else payloads[:FAST_JSON_PAYLOADS]


def _candidate_paths(product_id: str) -> list[str]:
    paths = [
        f'/produtos/{product_id}/imagens',
        f'/produtos/{product_id}/midia/imagens',
        f'/produtos/{product_id}/midias/imagens',
        f'/produtos/{product_id}/midia',
        f'/produtos/{product_id}/midias',
        f'/produtos/{product_id}/imagem',
        f'/produtos/{product_id}/anexos',
        f'/produtos/imagens/{product_id}',
        f'/produtos/midias/{product_id}',
    ]
    return paths if _deep_scan_enabled() else paths[:FAST_JSON_PATHS]


def _attempt_json(
    *,
    url_builder: Callable[[str], str],
    headers: dict[str, str],
    path: str,
    label: str,
    payload: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> None:
    methods = ('POST', 'PATCH') if not _deep_scan_enabled() else ('POST', 'PUT', 'PATCH')
    for method in methods:
        if not _deep_scan_enabled() and len(attempts) >= FAST_MAX_ATTEMPTS:
            return
        try:
            response = requests.request(method, url_builder(path), headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            attempts.append({
                'mode': 'image_endpoint_json',
                'method': method,
                'path': path,
                'label': label,
                'status': int(response.status_code),
                'payload_keys': sorted(payload.keys()),
                'response_preview': str(response.text or '')[:500],
            })
        except Exception as exc:
            attempts.append({'mode': 'image_endpoint_json', 'method': method, 'path': path, 'label': label, 'status': 'EXCEPTION', 'error': str(exc)[:220]})


def _attempt_multipart(
    *,
    url_builder: Callable[[str], str],
    headers: dict[str, str],
    path: str,
    probe: ImageProbe,
    attempts: list[dict[str, Any]],
) -> None:
    upload_headers = dict(headers)
    upload_headers.pop('Content-Type', None)
    files_variants = [('imagem', (probe.filename, probe.content, probe.mime)), ('arquivo', (probe.filename, probe.content, probe.mime))]
    data_variants = [{'url': probe.url}, {}]
    if _deep_scan_enabled():
        files_variants.extend([('file', (probe.filename, probe.content, probe.mime)), ('files', (probe.filename, probe.content, probe.mime))])
        data_variants.insert(0, {'link': probe.url, 'url': probe.url})
    for field, file_tuple in files_variants:
        for data in data_variants:
            if not _deep_scan_enabled() and len(attempts) >= FAST_MAX_ATTEMPTS:
                return
            try:
                response = requests.post(
                    url_builder(path),
                    headers=upload_headers,
                    files={field: file_tuple},
                    data=data,
                    timeout=15 if not _deep_scan_enabled() else 45,
                )
                attempts.append({
                    'mode': 'image_endpoint_multipart',
                    'method': 'POST',
                    'path': path,
                    'file_field': field,
                    'data_keys': sorted(data.keys()),
                    'status': int(response.status_code),
                    'mime': probe.mime,
                    'bytes': len(probe.content),
                    'response_preview': str(response.text or '')[:500],
                })
            except Exception as exc:
                attempts.append({'mode': 'image_endpoint_multipart', 'method': 'POST', 'path': path, 'file_field': field, 'status': 'EXCEPTION', 'error': str(exc)[:220]})


def _has_images(saved: dict[str, Any]) -> bool:
    midia = saved.get('midia') if isinstance(saved.get('midia'), dict) else {}
    imagens = saved.get('imagens') or midia.get('imagens')
    if isinstance(imagens, list):
        return any(bool(item) for item in imagens)
    if isinstance(imagens, dict):
        return any(_has_images({'imagens': value}) for value in imagens.values())
    return bool(imagens)


def push_product_images(
    *,
    product_id: str,
    payload: dict[str, Any],
    url_builder: Callable[[str], str],
    headers: dict[str, str],
    get_product: Callable[[str], dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    links = _image_links_from_payload(payload)
    attempts: list[dict[str, Any]] = []
    deep_scan = _deep_scan_enabled()
    add_audit_event(
        'bling_product_image_client_started',
        area='BLING_IMAGEM',
        status='INFO',
        details={'product_id': product_id, 'links': links, 'mode': 'deep_scan' if deep_scan else 'fast', 'responsible_file': RESPONSIBLE_FILE},
    )
    if not links:
        add_audit_event(
            'bling_product_image_client_no_links',
            area='BLING_IMAGEM',
            status='AVISO',
            details={'product_id': product_id, 'responsible_file': RESPONSIBLE_FILE},
        )
        return False, attempts

    for image_url in links:
        for path in _candidate_paths(product_id):
            for label, json_payload in _json_payloads(image_url):
                if not deep_scan and len(attempts) >= FAST_MAX_ATTEMPTS:
                    break
                _attempt_json(url_builder=url_builder, headers=headers, path=path, label=label, payload=json_payload, attempts=attempts)
            if not deep_scan and len(attempts) >= FAST_MAX_ATTEMPTS:
                break
        if not deep_scan:
            break

    # Fluxo normal: 1 GET final, sem travar. Multipart fica só no modo profundo.
    if not deep_scan:
        saved = get_product(product_id)
        ok = _has_images(saved)
        add_audit_event(
            'bling_product_image_client_fast_finished',
            area='BLING_IMAGEM',
            status='OK' if ok else 'AVISO',
            details={'product_id': product_id, 'has_images': ok, 'links': links, 'attempts': attempts[-12:], 'responsible_file': RESPONSIBLE_FILE},
        )
        return ok, attempts

    for image_url in links:
        saved = get_product(product_id)
        if _has_images(saved):
            add_audit_event(
                'bling_product_image_client_persisted_json',
                area='BLING_IMAGEM',
                status='OK',
                details={'product_id': product_id, 'image_url': image_url, 'attempts': attempts[-12:], 'responsible_file': RESPONSIBLE_FILE},
            )
            return True, attempts
        probe = _download_image(image_url, headers)
        attempts.append({'mode': 'image_download_probe', 'url': image_url, 'ok': probe.ok, 'mime': probe.mime, 'filename': probe.filename, 'bytes': len(probe.content), 'error': probe.error})
        if not probe.ok:
            continue
        for path in _candidate_paths(product_id):
            _attempt_multipart(url_builder=url_builder, headers=headers, path=path, probe=probe, attempts=attempts)
            saved = get_product(product_id)
            if _has_images(saved):
                add_audit_event(
                    'bling_product_image_client_persisted_multipart',
                    area='BLING_IMAGEM',
                    status='OK',
                    details={'product_id': product_id, 'path': path, 'image_url': image_url, 'attempts': attempts[-12:], 'responsible_file': RESPONSIBLE_FILE},
                )
                return True, attempts

    add_audit_event(
        'bling_product_image_client_not_persisted',
        area='BLING_IMAGEM',
        status='AVISO',
        details={'product_id': product_id, 'links': links, 'attempts': attempts[-30:], 'responsible_file': RESPONSIBLE_FILE},
    )
    return False, attempts


__all__ = ['push_product_images']
