from __future__ import annotations

from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_autocadastro_upsert.py'


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ('data', 'dados', 'items', 'result', 'results'):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return [payload] if payload.get('id') or payload.get('idProduto') else []


def _extract_product_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ('id', 'idProduto'):
            value = str(payload.get(key) or '').strip()
            if value:
                return value
        for key in ('data', 'dados', 'produto', 'result'):
            found = _extract_product_id(payload.get(key))
            if found:
                return found
    if isinstance(payload, list) and payload:
        return _extract_product_id(payload[0])
    return ''


def _identifiers_from_item(item: dict[str, Any]) -> list[str]:
    tributacao = item.get('tributacao') if isinstance(item.get('tributacao'), dict) else {}
    values = [
        item.get('codigo'), item.get('sku'), item.get('codigoProduto'),
        item.get('gtin'), item.get('ean'), item.get('codigoBarras'),
        tributacao.get('gtin'), tributacao.get('ean'), tributacao.get('codigoBarras'),
    ]
    out: list[str] = []
    for value in values:
        text = str(value or '').strip()
        if text and text.lower() not in {item.lower() for item in out}:
            out.append(text)
    return out


def _payload_candidates(payload: dict[str, Any]) -> list[str]:
    tributacao = payload.get('tributacao') if isinstance(payload.get('tributacao'), dict) else {}
    values = [payload.get('codigo'), payload.get('gtin'), tributacao.get('gtin')]
    out: list[str] = []
    for value in values:
        text = str(value or '').strip()
        if text and text.lower() not in {item.lower() for item in out}:
            out.append(text)
    return out


def resolve_product_id(
    token: dict[str, Any],
    payload: dict[str, Any],
    *,
    url_builder: Callable[[str], str],
    headers_builder: Callable[[dict[str, Any]], dict[str, str]],
    lookup_path: str = '/produtos',
    timeout: int = 20,
) -> str:
    headers = headers_builder(token)
    for candidate in _payload_candidates(payload):
        for params in ({'codigo': candidate}, {'criterio': candidate}, {'pesquisa': candidate}):
            try:
                response = requests.get(url_builder(lookup_path), headers=headers, params=params, timeout=timeout)
                if response.status_code >= 400:
                    continue
                items = _extract_items(response.json())
                loose_id = ''
                for item in items:
                    item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                    if not item_id:
                        continue
                    identifiers = [value.lower() for value in _identifiers_from_item(item)]
                    if candidate.lower() in identifiers:
                        return item_id
                    if len(items) == 1:
                        loose_id = item_id
                if loose_id:
                    return loose_id
            except Exception as exc:
                add_audit_event('bling_autocadastro_lookup_exception', area='AUTOCADASTRO', status='AVISO', details={'candidate': candidate, 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
    return ''


def upsert_product(
    token: dict[str, Any],
    payload: dict[str, Any],
    *,
    url_builder: Callable[[str], str],
    headers_builder: Callable[[dict[str, Any]], dict[str, str]],
    lookup_path: str = '/produtos',
    create_path: str = '/produtos',
    update_path: str = '/produtos/{id}',
    update_method: str = 'PUT',
    timeout: int = 30,
) -> tuple[str, str, str]:
    product_id = resolve_product_id(token, payload, url_builder=url_builder, headers_builder=headers_builder, lookup_path=lookup_path, timeout=min(timeout, 20))
    headers = headers_builder(token)
    if product_id:
        path = str(update_path or '/produtos/{id}').replace('{id}', product_id)
        try:
            response = requests.request((update_method or 'PUT').upper(), url_builder(path), headers=headers, json=payload, timeout=timeout)
            if response.status_code < 400:
                return product_id, '', 'updated'
            return '', f'Atualização recusada ({response.status_code}) para ID {product_id}: {str(response.text or "")[:260]}', 'update_failed'
        except Exception as exc:
            return '', f'Falha técnica na atualização do produto ID {product_id}: {exc}', 'update_failed'

    try:
        response = requests.post(url_builder(create_path or '/produtos'), headers=headers, json=payload, timeout=timeout)
        if response.status_code >= 400:
            resolved_after_error = resolve_product_id(token, payload, url_builder=url_builder, headers_builder=headers_builder, lookup_path=lookup_path, timeout=min(timeout, 20))
            if resolved_after_error:
                path = str(update_path or '/produtos/{id}').replace('{id}', resolved_after_error)
                retry = requests.request((update_method or 'PUT').upper(), url_builder(path), headers=headers, json=payload, timeout=timeout)
                if retry.status_code < 400:
                    return resolved_after_error, '', 'updated_after_create_conflict'
            return '', f'Cadastro recusado ({response.status_code}): {str(response.text or "")[:260]}', 'create_failed'
        product_id = _extract_product_id(response.json() if str(response.text or '').strip() else {})
        if not product_id:
            return '', 'Cadastro aceito, mas a API não retornou o ID do produto.', 'created_without_id'
        return product_id, '', 'created'
    except Exception as exc:
        return '', f'Falha técnica no cadastro: {exc}', 'create_failed'


__all__ = ['resolve_product_id', 'upsert_product']
