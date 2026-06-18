from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.brand_title_detector import detect_brand_from_title

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_v3_product_client.py'
DEFAULT_BRAND = 'Genérico'


@dataclass(frozen=True)
class BlingV3Result:
    ok: bool
    product_id: str
    status: str
    attempts: tuple[dict[str, Any], ...]
    persisted: dict[str, Any]


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).startswith('_') or str(key).startswith('bling_review_'):
                continue
            cleaned = _clean(item)
            if cleaned not in ('', None, {}, []):
                out[key] = cleaned
        return out
    if isinstance(value, list):
        return [item for item in (_clean(item) for item in value) if item not in ('', None, {}, [])]
    return value


def _extract_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    for key in ('data', 'dados', 'produto', 'result'):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


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


def _product_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ('id', 'idProduto'):
            value = str(payload.get(key) or '').strip()
            if value:
                return value
        for key in ('data', 'dados', 'produto', 'result'):
            found = _product_id(payload.get(key))
            if found:
                return found
    if isinstance(payload, list) and payload:
        return _product_id(payload[0])
    return ''


def _image_links(payload: dict[str, Any]) -> list[str]:
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
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            value = str(item.get('link') or item.get('url') or item.get('URL') or '').strip()
        else:
            value = str(item or '').strip()
        if value.startswith(('http://', 'https://')) and value not in out:
            out.append(value)
    return out[:10]


def _fields(payload: dict[str, Any]) -> list[str]:
    fields: set[str] = set(str(key) for key in payload.keys())
    if 'midia' in payload or 'imagens' in payload:
        fields.add('imagens')
    for parent in ('tributacao', 'categoria', 'dimensoes'):
        if isinstance(payload.get(parent), dict):
            for key in payload[parent].keys():
                fields.add(f'{parent}_{key}')
    if isinstance(payload.get('midia'), dict) and isinstance(payload['midia'].get('video'), dict):
        fields.add('video_url')
    return sorted(fields)


def _infer_brand(nome: str) -> str:
    return detect_brand_from_title(nome)


def _safe_brand(value: Any, nome: str) -> str:
    current = str(value or '').strip()
    if current.lower() in {'generico', 'genérico'}:
        return DEFAULT_BRAND
    detected = detect_brand_from_title('', fallback=current)
    if detected:
        return detected
    detected = detect_brand_from_title(nome)
    return detected or DEFAULT_BRAND


def _first_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(payload.get(key) or '').strip()
        if value:
            return value
    return ''


def _force_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload)
    nome = str(out.get('nome') or '').strip()
    descricao = str(out.get('descricaoCurta') or out.get('descricao') or '').strip()
    if nome and not descricao:
        descricao = nome
    if descricao:
        out['descricaoCurta'] = descricao
        out.setdefault('descricaoComplementar', descricao)
    out['marca'] = _safe_brand(out.get('marca'), nome)
    out.setdefault('tipo', 'P')
    out.setdefault('situacao', 'A')
    out.setdefault('formato', 'S')
    out.setdefault('unidade', 'UN')
    out.setdefault('pesoLiquido', 0.300)
    out.setdefault('pesoBruto', 0.300)
    out.setdefault('volumes', 1)
    out.setdefault('itensPorCaixa', 1)
    if not isinstance(out.get('categoria'), dict):
        categoria = str(out.get('categoria') or '').strip()
        if categoria:
            out['categoria'] = {'descricao': categoria}
    dimensoes = out.get('dimensoes') if isinstance(out.get('dimensoes'), dict) else {}
    dimensoes.setdefault('largura', 11)
    dimensoes.setdefault('altura', 2)
    dimensoes.setdefault('profundidade', 16)
    out['dimensoes'] = dimensoes
    link_externo = _first_text(out, ('linkExterno', 'urlProduto', 'url', 'link'))
    if link_externo.startswith(('http://', 'https://')):
        out.setdefault('linkExterno', link_externo)
    link_video = _first_text(out, ('linkVideo', 'video', 'urlVideo'))
    if link_video:
        out.setdefault('linkVideo', link_video)
        midia = out.get('midia') if isinstance(out.get('midia'), dict) else {}
        midia.setdefault('video', {'url': link_video})
        out['midia'] = midia
    return _clean(out)


def _media_payloads(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    links = _image_links(payload)
    if not links:
        return []
    by_link = [{'link': link} for link in links]
    by_url = [{'url': link} for link in links]
    by_both = [{'link': link, 'url': link} for link in links]
    as_strings = list(links)
    return [
        ('media.midia.imagens.imagensURL.link', {'midia': {'imagens': {'imagensURL': by_link}}}),
        ('media.midia.imagens.imagensURL.url', {'midia': {'imagens': {'imagensURL': by_url}}}),
        ('media.midia.imagens.imagensURL.link_url', {'midia': {'imagens': {'imagensURL': by_both}}}),
        ('media.midia.imagens.imagensURL.strings', {'midia': {'imagens': {'imagensURL': as_strings}}}),
        ('media.midia.imagens.link', {'midia': {'imagens': by_link}}),
        ('media.midia.imagens.url', {'midia': {'imagens': by_url}}),
        ('media.midia.imagens.link_url', {'midia': {'imagens': by_both}}),
        ('media.midia.imagens.externas.link', {'midia': {'imagens': {'externas': by_link}}}),
        ('media.midia.imagens.externas.url', {'midia': {'imagens': {'externas': by_url}}}),
        ('media.imagens.root.link', {'imagens': by_link}),
        ('media.imagens.root.url', {'imagens': by_url}),
    ]


def _description_payloads(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    value = str(payload.get('descricaoCurta') or payload.get('descricaoComplementar') or payload.get('nome') or '').strip()
    if not value:
        return []
    return [
        ('description.descricaoCurta', {'descricaoCurta': value}),
        ('description.descricaoComplementar', {'descricaoComplementar': value}),
        ('description.dual', {'descricaoCurta': value, 'descricaoComplementar': value}),
    ]


def _detail_payloads(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    if payload.get('marca'):
        out.append(('field.marca', {'marca': payload['marca']}))
    if payload.get('categoria'):
        out.append(('field.categoria', {'categoria': payload['categoria']}))
    if payload.get('linkExterno'):
        out.append(('field.linkExterno', {'linkExterno': payload['linkExterno']}))
        out.append(('field.urlProduto', {'urlProduto': payload['linkExterno']}))
    if payload.get('linkVideo'):
        out.append(('field.linkVideo', {'linkVideo': payload['linkVideo']}))
        out.append(('field.midia.video', {'midia': {'video': {'url': payload['linkVideo']}}}))
    physical = _clean({
        'pesoLiquido': payload.get('pesoLiquido'),
        'pesoBruto': payload.get('pesoBruto'),
        'dimensoes': payload.get('dimensoes'),
        'volumes': payload.get('volumes'),
        'itensPorCaixa': payload.get('itensPorCaixa'),
    })
    if physical:
        out.append(('field.physical.all', physical))
    for key in ('pesoLiquido', 'pesoBruto', 'volumes', 'itensPorCaixa'):
        if payload.get(key) not in ('', None, {}, []):
            out.append((f'field.{key}', {key: payload[key]}))
    if isinstance(payload.get('dimensoes'), dict):
        out.append(('field.dimensoes', {'dimensoes': payload['dimensoes']}))
        for key, value in payload['dimensoes'].items():
            out.append((f'field.dimensoes.{key}', {'dimensoes': {key: value}}))
    return [(label, _clean(item)) for label, item in out if _clean(item)]


def _has_non_empty_images(imagens: Any) -> bool:
    if isinstance(imagens, list):
        return any(bool(item) for item in imagens)
    if isinstance(imagens, dict):
        return any(_has_non_empty_images(value) for value in imagens.values())
    return bool(imagens)


def _nonzero(value: Any) -> bool:
    try:
        return float(value) != 0.0
    except Exception:
        return value not in (None, '', 0, 0.0)


def _persistence_report(saved: dict[str, Any]) -> dict[str, Any]:
    midia = saved.get('midia') if isinstance(saved.get('midia'), dict) else {}
    imagens = saved.get('imagens') or midia.get('imagens')
    dimensoes = saved.get('dimensoes') if isinstance(saved.get('dimensoes'), dict) else {}
    video = midia.get('video') if isinstance(midia.get('video'), dict) else {}
    return {
        'saved_keys': sorted(saved.keys()),
        'nome': bool(saved.get('nome')),
        'codigo': bool(saved.get('codigo')),
        'preco': saved.get('preco') not in (None, ''),
        'descricaoCurta': bool(saved.get('descricaoCurta')),
        'descricaoComplementar': bool(saved.get('descricaoComplementar')),
        'marca': bool(saved.get('marca')),
        'marca_value': str(saved.get('marca') or '')[:120],
        'categoria': bool(saved.get('categoria')),
        'categoria_preview': str(saved.get('categoria') or '')[:300],
        'linkExterno': bool(saved.get('linkExterno') or saved.get('urlProduto')),
        'linkVideo': bool(saved.get('linkVideo') or video.get('url')),
        'midia': bool(midia),
        'imagens': _has_non_empty_images(imagens),
        'pesoLiquido': _nonzero(saved.get('pesoLiquido')),
        'pesoBruto': _nonzero(saved.get('pesoBruto')),
        'volumes': _nonzero(saved.get('volumes')),
        'itensPorCaixa': _nonzero(saved.get('itensPorCaixa')),
        'dimensoes': bool(dimensoes) and any(_nonzero(value) for value in dimensoes.values()),
        'dimensoes_keys': sorted(dimensoes.keys()) if isinstance(dimensoes, dict) else [],
        'midia_type': type(midia).__name__,
        'imagens_type': type(imagens).__name__,
        'midia_preview': str(midia)[:700],
        'imagens_preview': str(imagens)[:700],
    }


class BlingV3ProductClient:
    def __init__(
        self,
        *,
        token: dict[str, Any],
        url_builder: Callable[[str], str],
        headers_builder: Callable[[dict[str, Any]], dict[str, str]],
        timeout: int = 30,
    ) -> None:
        self.token = token
        self.url_builder = url_builder
        self.headers = headers_builder(token)
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], str]:
        response = requests.request(
            method.upper(),
            self.url_builder(path),
            headers=self.headers,
            json=payload if payload is not None else None,
            timeout=self.timeout,
        )
        data: dict[str, Any] = {}
        try:
            data = response.json() if str(response.text or '').strip() else {}
        except Exception:
            data = {}
        return int(response.status_code), data, str(response.text or '')[:700]

    def get_product(self, product_id: str) -> dict[str, Any]:
        status, data, text = self.request('GET', f'/produtos/{product_id}')
        saved = _extract_data(data)
        add_audit_event(
            'bling_v3_product_get',
            area='BLING_API_V3',
            status='OK' if status < 400 else 'AVISO',
            details={'product_id': product_id, 'status_code': status, 'persistence': _persistence_report(saved), 'response_preview': text[:300], 'responsible_file': RESPONSIBLE_FILE},
        )
        return saved

    def find_product_id(self, candidates: list[str]) -> str:
        for candidate in candidates:
            value = str(candidate or '').strip()
            if not value:
                continue
            for params in ({'codigo': value}, {'criterio': value}, {'pesquisa': value}):
                try:
                    response = requests.get(self.url_builder('/produtos'), headers=self.headers, params=params, timeout=self.timeout)
                    if response.status_code >= 400:
                        continue
                    items = _extract_items(response.json())
                    for item in items:
                        item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                        identifiers = [str(item.get(key) or '').strip().lower() for key in ('codigo', 'sku', 'gtin', 'ean', 'codigoBarras')]
                        tributacao = item.get('tributacao') if isinstance(item.get('tributacao'), dict) else {}
                        identifiers.extend(str(tributacao.get(key) or '').strip().lower() for key in ('gtin', 'ean', 'codigoBarras'))
                        if item_id and value.lower() in identifiers:
                            return item_id
                    if len(items) == 1:
                        item_id = str(items[0].get('id') or items[0].get('idProduto') or '').strip()
                        if item_id:
                            return item_id
                except Exception:
                    continue
        return ''

    def create_product(self, payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        final_payload = _force_defaults(payload)
        status, data, text = self.request('POST', '/produtos', final_payload)
        product_id = _product_id(data)
        attempt = {'method': 'POST', 'path': '/produtos', 'status': status, 'payload_keys': sorted(final_payload.keys()), 'changed_fields': _fields(final_payload), 'response_preview': text}
        if status < 400 and product_id:
            self._after_write(product_id, final_payload, [attempt])
            return product_id, [attempt]
        return '', [attempt]

    def update_product(self, product_id: str, payload: dict[str, Any]) -> BlingV3Result:
        attempts: list[dict[str, Any]] = []
        final_payload = _force_defaults(payload)
        options: list[tuple[str, dict[str, Any]]] = [
            ('product.full.put', final_payload),
            ('product.full.patch', final_payload),
        ]
        no_media = deepcopy(final_payload)
        no_media.pop('midia', None)
        no_media.pop('imagens', None)
        if no_media != final_payload:
            options.append(('product.no_media.patch', _clean(no_media)))
        options.extend(_description_payloads(final_payload))
        options.extend(_detail_payloads(final_payload))
        options.extend(_media_payloads(final_payload))

        for label, item in options:
            method = 'PUT' if label.endswith('.put') else 'PATCH'
            status, data, text = self.request(method, f'/produtos/{product_id}', item)
            attempts.append({'method': method, 'path': f'/produtos/{product_id}', 'label': label, 'status': status, 'payload_keys': sorted(item.keys()), 'changed_fields': _fields(item), 'response_preview': text})
            if status in {401, 403, 404}:
                break

        persisted = self._after_write(product_id, final_payload, attempts)
        return BlingV3Result(ok=any(isinstance(a.get('status'), int) and int(a.get('status')) < 400 for a in attempts), product_id=product_id, status='updated', attempts=tuple(attempts), persisted=persisted)

    def upsert_product(self, payload: dict[str, Any]) -> BlingV3Result:
        final_payload = _force_defaults(payload)
        candidates = [str(final_payload.get('codigo') or ''), str(final_payload.get('gtin') or ''), str((final_payload.get('tributacao') or {}).get('gtin') or '')]
        product_id = self.find_product_id(candidates)
        if product_id:
            return self.update_product(product_id, final_payload)
        created_id, attempts = self.create_product(final_payload)
        persisted = self.get_product(created_id) if created_id else {}
        return BlingV3Result(ok=bool(created_id), product_id=created_id, status='created' if created_id else 'failed', attempts=tuple(attempts), persisted=persisted)

    def _after_write(self, product_id: str, payload: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
        saved = self.get_product(product_id)
        report = _persistence_report(saved)
        expected = _fields(payload)
        add_audit_event(
            'bling_v3_product_write_verified',
            area='BLING_API_V3',
            status='OK' if report.get('nome') and report.get('codigo') else 'AVISO',
            details={
                'product_id': product_id,
                'attempts': attempts[-24:],
                'expected_image_links': _image_links(payload),
                'expected_fields': expected,
                'persistence': report,
                'not_persisted_expected_flags': [field for field in ('descricaoCurta', 'descricaoComplementar', 'marca', 'categoria', 'linkExterno', 'linkVideo', 'imagens', 'pesoLiquido', 'pesoBruto', 'dimensoes', 'volumes', 'itensPorCaixa') if field in expected or field in ('imagens', 'dimensoes') and report.get(field) is False],
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return saved


__all__ = ['BlingV3ProductClient', 'BlingV3Result']
