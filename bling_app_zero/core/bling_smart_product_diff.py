from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_smart_product_diff.py'

_IMAGE_VARIANT_RE = re.compile(
    r'(?:[-_](?:\d{2,5}x\d{2,5}|\d{2,5}w|\d{2,5}h|small|medium|large|thumb|thumbnail|scaled|resize|resized|original|webp|jpg|jpeg|png|avif))*$',
    re.IGNORECASE,
)
_IMAGE_HASH_RE = re.compile(r'[-_][a-f0-9]{8,32}$', re.IGNORECASE)
_GENERIC_NAME_RE = re.compile(r'^(produto|produto sem nome|sem nome|item|mercadoria)\b', re.IGNORECASE)
_BLOCKED_BRAND_TERMS = ('mega center', 'megacenter', 'stoqui', 'loja', 'eletronicos', 'eletrônicos')

_FIELD_TO_PAYLOAD_PATH: dict[str, tuple[str, ...]] = {
    'nome': ('nome',),
    'codigo': ('codigo',),
    'preco': ('preco',),
    'descricaoCurta': ('descricaoCurta',),
    'marca': ('marca',),
    'unidade': ('unidade',),
    'formato': ('formato',),
    'situacao': ('situacao',),
    'ncm': ('tributacao', 'ncm'),
    'gtin': ('gtin',),
    'tributacao_gtin': ('tributacao', 'gtin'),
    'categoria_id': ('categoria', 'id'),
    'categoria_descricao': ('categoria', 'descricao'),
    'imagens': ('midia', 'imagens'),
}
_PROTECTED_WHEN_EXISTING_FIELDS = {'codigo', 'gtin', 'tributacao_gtin'}
_ALWAYS_SAFE_FIELDS = {'preco', 'unidade', 'formato', 'situacao', 'ncm', 'categoria_id', 'categoria_descricao'}


def _extract_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        for key in ('data', 'dados', 'produto', 'result'):
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
    text = str(value or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
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


def _get_path(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return ''
        current = current.get(key)
    return current


def _set_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    if value in ('', None, {}, []):
        return
    current = target
    for key in path[:-1]:
        nested = current.get(key)
        if not isinstance(nested, dict):
            nested = {}
            current[key] = nested
        current = nested
    current[path[-1]] = deepcopy(value)


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
        for part in re.split(r'[|;,\n]\s*', value):
            if part.strip():
                images.append(part.strip())
    clean: list[str] = []
    for item in images:
        text = str(item or '').strip()
        if text and text not in clean:
            clean.append(text)
    return clean


def _image_keys(value: Any) -> list[str]:
    keys: list[str] = []
    for item in _images_from_any(value):
        key = _image_key(item)
        if key and key not in keys:
            keys.append(key)
    return sorted(keys)


def _cmp_images(value: Any) -> str:
    return '|'.join(_image_keys(value))


def _existing_comparable(existing: dict[str, Any]) -> dict[str, str]:
    tributacao = existing.get('tributacao') if isinstance(existing.get('tributacao'), dict) else {}
    categoria = existing.get('categoria') if isinstance(existing.get('categoria'), dict) else {}
    return {
        'nome': _cmp_text(existing.get('nome') or existing.get('descricao')),
        'codigo': _cmp_text(existing.get('codigo') or existing.get('sku')),
        'preco': _cmp_number(existing.get('preco') or existing.get('precoVenda')),
        'descricaoCurta': _cmp_text(existing.get('descricaoCurta') or existing.get('descricaoComplementar') or existing.get('descricao')),
        'marca': _cmp_text(existing.get('marca')),
        'unidade': _cmp_text(existing.get('unidade')),
        'formato': _cmp_text(existing.get('formato')),
        'situacao': _cmp_text(existing.get('situacao')),
        'ncm': _cmp_text(tributacao.get('ncm') or existing.get('ncm')),
        'gtin': _cmp_text(existing.get('gtin') or existing.get('ean') or existing.get('codigoBarras')),
        'tributacao_gtin': _cmp_text(tributacao.get('gtin') or tributacao.get('ean')),
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
        'gtin': _cmp_text(payload.get('gtin')),
        'tributacao_gtin': _cmp_text(tributacao.get('gtin')),
        'categoria_id': _cmp_text(categoria.get('id')),
        'categoria_descricao': _cmp_text(categoria.get('descricao') or categoria.get('nome')),
        'imagens': _cmp_images(payload.get('midia') or payload.get('imagens') or payload.get('images')),
    }


def _raw_existing_value(existing: dict[str, Any], field: str) -> Any:
    if field == 'nome':
        return existing.get('nome') or existing.get('descricao')
    if field == 'codigo':
        return existing.get('codigo') or existing.get('sku')
    if field == 'preco':
        return existing.get('preco') or existing.get('precoVenda')
    if field == 'descricaoCurta':
        return existing.get('descricaoCurta') or existing.get('descricaoComplementar') or existing.get('descricao')
    if field == 'ncm':
        return _dig(existing, 'tributacao', 'ncm') or existing.get('ncm')
    if field == 'gtin':
        return existing.get('gtin') or existing.get('ean') or existing.get('codigoBarras')
    if field == 'tributacao_gtin':
        return _dig(existing, 'tributacao', 'gtin') or _dig(existing, 'tributacao', 'ean')
    if field == 'categoria_id':
        return _dig(existing, 'categoria', 'id') or existing.get('idCategoria')
    if field == 'categoria_descricao':
        return _dig(existing, 'categoria', 'descricao') or _dig(existing, 'categoria', 'nome') or existing.get('categoria')
    if field == 'imagens':
        return existing.get('midia') or existing.get('imagens') or existing.get('images')
    return existing.get(field)


def _raw_payload_value(payload: dict[str, Any], field: str) -> Any:
    path = _FIELD_TO_PAYLOAD_PATH.get(field)
    if path:
        return _get_path(payload, path)
    return payload.get(field)


def _text_quality(value: Any) -> int:
    text = _clean_text(value)
    if not text:
        return 0
    words = re.findall(r'[A-Za-zÀ-ÿ0-9]{2,}', text)
    score = min(len(text), 5000) + min(len(words), 500) * 3
    if _GENERIC_NAME_RE.search(text):
        score -= 120
    return max(score, 0)


def _brand_is_safe(value: Any) -> bool:
    brand = _clean_text(value)
    low = brand.lower()
    return bool(brand) and 2 <= len(brand) <= 60 and not any(term in low for term in _BLOCKED_BRAND_TERMS)


def _field_should_update(field: str, existing: dict[str, Any], payload: dict[str, Any], *, old_cmp: str, new_cmp: str) -> bool:
    if not new_cmp or old_cmp == new_cmp:
        return False
    old_raw = _raw_existing_value(existing, field)
    new_raw = _raw_payload_value(payload, field)
    if field in _PROTECTED_WHEN_EXISTING_FIELDS:
        return not bool(old_cmp)
    if field == 'nome':
        new_name = _clean_text(new_raw)
        old_name = _clean_text(old_raw)
        if len(new_name) < 3 or _GENERIC_NAME_RE.search(new_name):
            return False
        if old_name and len(new_name) + 10 < len(old_name) * 0.65:
            return False
        return True
    if field == 'descricaoCurta':
        old_score = _text_quality(old_raw)
        new_score = _text_quality(new_raw)
        if not new_score:
            return False
        if not old_score:
            return True
        return new_score >= max(int(old_score * 1.08), old_score + 30)
    if field == 'marca':
        if not _brand_is_safe(new_raw):
            return False
        if not old_cmp:
            return True
        return not _brand_is_safe(old_raw)
    if field == 'imagens':
        old_keys = set(_image_keys(old_raw))
        new_keys = set(_image_keys(new_raw))
        if not new_keys or old_keys == new_keys:
            return False
        if old_keys and len(new_keys) < max(1, len(old_keys) - 1) and not (new_keys - old_keys):
            return False
        return True
    if field in _ALWAYS_SAFE_FIELDS:
        return True
    return True


def _changed_fields(existing: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    old = _existing_comparable(existing)
    new = _payload_comparable(payload)
    changed: list[str] = []
    for field, new_value in new.items():
        old_value = old.get(field, '')
        if _field_should_update(field, existing, payload, old_cmp=old_value, new_cmp=new_value):
            changed.append(field)
    return changed


def _selective_update_payload(payload: dict[str, Any], changed_fields: list[str]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for field in changed_fields:
        path = _FIELD_TO_PAYLOAD_PATH.get(field)
        if not path:
            continue
        value = _get_path(payload, path)
        if value in ('', None, {}, []):
            continue
        _set_path(selected, path, value)
    for key in ('tributacao', 'categoria'):
        if isinstance(selected.get(key), dict):
            selected[key] = {k: v for k, v in selected[key].items() if v not in ('', None, {}, [])}
            if not selected[key]:
                selected.pop(key, None)
    return selected


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
            add_audit_event(
                'bling_smart_product_detail_fetch_failed',
                area='BLING_ENVIO',
                status='AVISO',
                details={'product_id': product_id, 'status': int(response.status_code), 'responsible_file': RESPONSIBLE_FILE},
            )
            return {}
        return _extract_dict(response.json())
    except Exception as exc:
        add_audit_event(
            'bling_smart_product_detail_fetch_exception',
            area='BLING_ENVIO',
            status='AVISO',
            details={'product_id': product_id, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE},
        )
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
        changed = _changed_fields(existing, payload) if existing else list(_payload_comparable(payload).keys())
        update_payload = _selective_update_payload(payload, changed) if existing else dict(payload)
        if existing and not update_payload:
            attempts.append({
                'mode': 'skip_unchanged_or_not_better',
                'product_id': product_id,
                'strategy': strategy,
                'status': 'UNCHANGED_OR_NOT_BETTER',
                'confidence': meta.get('confidence'),
                'changed_fields': [],
            })
            add_audit_event(
                'bling_smart_product_unchanged_skipped',
                area='BLING_ENVIO',
                status='PULADO',
                details={'product_id': product_id, 'strategy': strategy, 'reason': 'sem_diferenca_real_ou_dado_novo_pior', 'responsible_file': responsible_file},
            )
            return 'unchanged', attempts

        methods = ('PATCH', 'PUT') if existing else ('PUT', 'PATCH')
        for method in methods:
            try:
                response = requests.request(
                    method,
                    url_builder(f'/produtos/{product_id}'),
                    headers=headers_builder(token),
                    json=update_payload,
                    timeout=timeout,
                )
                attempts.append({
                    'mode': 'update_existing_selective',
                    'method': method,
                    'product_id': product_id,
                    'strategy': strategy,
                    'status': int(response.status_code),
                    'confidence': meta.get('confidence'),
                    'changed_fields': changed,
                    'payload_keys': sorted(update_payload.keys()),
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
                            'payload_keys': sorted(update_payload.keys()),
                            'mode': 'selective_update_only_changed_fields',
                            'responsible_file': responsible_file,
                        },
                    )
                    return 'updated', attempts
                if response.status_code in {401, 403, 404}:
                    break
            except Exception as exc:
                attempts.append({
                    'mode': 'update_existing_selective',
                    'method': method,
                    'product_id': product_id,
                    'strategy': strategy,
                    'status': 'EXCEPTION',
                    'changed_fields': changed,
                    'payload_keys': sorted(update_payload.keys()),
                    'error': str(exc)[:240],
                })
    return 'failed', attempts


__all__ = ['fetch_existing_product_detail', 'update_existing_product_if_changed']
