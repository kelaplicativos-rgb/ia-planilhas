from __future__ import annotations

import json
import os
import re
from urllib.parse import urljoin, urlparse, urlunparse

import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell
from bling_app_zero.engines.fast_site_scraper.models import FastProductData

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/openai_catalog_fallback.py'
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
DEFAULT_OPENAI_MODEL = 'gpt-4.1'
BLOCKED_URL_TERMS = (
    '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos',
    'facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '#',
)


def _streamlit_openai_secret(name: str) -> str:
    try:
        import streamlit as st  # type: ignore
        value = st.secrets.get('openai', {}).get(name) if hasattr(st, 'secrets') else ''
        return str(value or '').strip()
    except Exception:
        return ''


def _openai_api_key() -> str:
    return (
        os.getenv('MAPEIAAI_OPENAI_API_KEY', '').strip()
        or os.getenv('OPENAI_API_KEY', '').strip()
        or _streamlit_openai_secret('api_key')
    )


def _openai_model() -> str:
    return (
        os.getenv('MAPEIAAI_OPENAI_MODEL', '').strip()
        or _streamlit_openai_secret('model')
        or DEFAULT_OPENAI_MODEL
    )


def _norm_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def _same_domain(url: str, base: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    root = urlparse(base).netloc.lower().replace('www.', '')
    return bool(host and root and (host == root or host.endswith('.' + root)))


def _allowed_product_url(url: str, base_url: str) -> bool:
    low = str(url or '').lower()
    return (
        url.startswith(('http://', 'https://'))
        and _same_domain(url, base_url)
        and not any(term in low for term in BLOCKED_URL_TERMS)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def _clean_price(value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    matches = re.findall(r'(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', text)
    return matches[-1] if matches else text[:40]


def _response_text(payload: dict) -> str:
    text = payload.get('output_text')
    if isinstance(text, str) and text.strip():
        return text
    chunks: list[str] = []
    for item in payload.get('output') or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content') or []:
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                chunks.append(content['text'])
    return ''.join(chunks).strip()


def _schema() -> dict[str, object]:
    return {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'products': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'url': {'type': 'string'},
                        'codigo': {'type': 'string'},
                        'gtin': {'type': 'string'},
                        'descricao': {'type': 'string'},
                        'preco': {'type': 'string'},
                        'estoque': {'type': 'string'},
                        'imagem': {'type': 'string'},
                        'marca': {'type': 'string'},
                        'categoria': {'type': 'string'},
                    },
                    'required': ['url', 'codigo', 'gtin', 'descricao', 'preco', 'estoque', 'imagem', 'marca', 'categoria'],
                },
            },
        },
        'required': ['products'],
    }


def openai_catalog_products(base_url: str, limit: int = 40) -> list[FastProductData]:
    """Fallback para lojas que bloqueiam fetch direto do servidor.

    Usa web search da Responses API para localizar páginas públicas do domínio
    informado e retorna apenas URLs validadas no mesmo domínio.
    """
    key = _openai_api_key()
    base = _norm_url(base_url)
    if not key or not base:
        return []

    host = urlparse(base).netloc.lower().replace('www.', '')
    prompt = (
        'Busque produtos públicos reais do fornecedor/e-commerce abaixo. '
        'Use web search se necessário. Retorne somente produtos encontrados no mesmo domínio, '
        'com URL canônica pública, nome e preço quando disponível. Ignore categorias, banners, login, carrinho, redes sociais e páginas institucionais. '
        f'Domínio permitido: {host}. URL inicial: {base}. Retorne no máximo {int(limit)} produtos.'
    )
    payload = {
        'model': _openai_model(),
        'instructions': 'Você é um extrator de catálogo. Responda somente no JSON schema solicitado, sem comentários. Não invente produtos; use somente páginas públicas encontradas.',
        'input': prompt,
        'tools': [{'type': 'web_search_preview', 'search_context_size': 'medium'}],
        'tool_choice': 'auto',
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'public_catalog_products',
                'schema': _schema(),
                'strict': False,
            },
        },
        'temperature': 0,
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=45,
        )
        if response.status_code >= 400:
            add_audit_event(
                'site_scraper_openai_catalog_fallback',
                area='SITE',
                step='entrada',
                status='AVISO',
                details={'status_code': response.status_code, 'products': 0, 'responsible_file': RESPONSIBLE_FILE},
            )
            return []
        raw_text = _response_text(response.json())
        data = json.loads(raw_text) if raw_text else {}
    except Exception as exc:
        add_audit_event(
            'site_scraper_openai_catalog_fallback',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={'error': type(exc).__name__, 'products': 0, 'responsible_file': RESPONSIBLE_FILE},
        )
        return []

    products: list[FastProductData] = []
    seen: set[str] = set()
    for item in data.get('products') or []:
        if not isinstance(item, dict):
            continue
        url = _norm_url(urljoin(base, clean_cell(item.get('url') or '')))
        if not url or not _allowed_product_url(url, base):
            continue
        descricao = clean_cell(item.get('descricao') or '')[:240]
        if not descricao or url in seen:
            continue
        seen.add(url)
        products.append(FastProductData(
            url=url,
            codigo=clean_cell(item.get('codigo') or ''),
            gtin=clean_cell(item.get('gtin') or ''),
            descricao=descricao,
            preco=_clean_price(item.get('preco') or ''),
            estoque=clean_cell(item.get('estoque') or ''),
            imagem=clean_cell(urljoin(base, clean_cell(item.get('imagem') or ''))),
            marca=clean_cell(item.get('marca') or ''),
            categoria=clean_cell(item.get('categoria') or ''),
        ))
        if len(products) >= limit:
            break

    add_audit_event(
        'site_scraper_openai_catalog_fallback',
        area='SITE',
        step='entrada',
        status='OK' if products else 'INFO',
        details={'products': len(products), 'domain': host, 'responsible_file': RESPONSIBLE_FILE},
    )
    return products


__all__ = ['openai_catalog_products']
