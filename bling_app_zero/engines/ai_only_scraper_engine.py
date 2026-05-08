from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_CONTEXT_CHARS = 18000
MAX_ANCHORS = 450
MAX_WORKERS = 8

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
}


@dataclass(frozen=True)
class AiPage:
    url: str
    html: str
    text: str
    title: str
    anchors: list[dict[str, str]]
    jsonld: list[str]


def split_urls(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r'[\n,;]+', str(raw or '')) if item.strip().startswith(('http://', 'https://'))]


def _unique_names(*names: str) -> list[str]:
    result: list[str] = []
    for name in names:
        for candidate in [name, str(name).upper(), str(name).lower()]:
            if candidate and candidate not in result:
                result.append(candidate)
    return result


def _secret_value(*names: str) -> str:
    expanded_names = _unique_names(*names)
    for name in expanded_names:
        value = os.getenv(name)
        if value:
            return str(value).strip()

    try:
        for name in expanded_names:
            if name in st.secrets and st.secrets.get(name):
                return str(st.secrets.get(name) or '').strip()
    except Exception:
        pass

    try:
        section = st.secrets.get('openai', {})
        if isinstance(section, dict):
            for name in expanded_names:
                if name in section and section.get(name):
                    return str(section.get(name) or '').strip()
            wants_key = any('key' in normalize_key(name) or 'token' in normalize_key(name) for name in expanded_names)
            wants_model = any('model' in normalize_key(name) for name in expanded_names)
            if wants_key:
                for alias in ['api_key', 'key', 'token', 'OPENAI_API_KEY', 'openai_api_key']:
                    if alias in section and section.get(alias):
                        return str(section.get(alias) or '').strip()
            if wants_model:
                for alias in ['model', 'OPENAI_MODEL', 'openai_model']:
                    if alias in section and section.get(alias):
                        return str(section.get(alias) or '').strip()
    except Exception:
        pass
    return ''


def ai_available() -> bool:
    return bool(_secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key'))


def _model_name() -> str:
    return _secret_value('OPENAI_MODEL', 'openai_model', 'model') or DEFAULT_MODEL


def _normalize_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def _same_domain(url: str, base_url: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    base = urlparse(base_url).netloc.lower().replace('www.', '')
    return host == base or host.endswith('.' + base)


def _safe_get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if response.status_code in {403, 406, 429}:
            alt_headers = dict(HEADERS)
            alt_headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36'
            response = requests.get(url, headers=alt_headers, timeout=25, allow_redirects=True)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _make_page(url: str) -> AiPage | None:
    normalized = _normalize_url(url)
    if not normalized:
        return None
    html = _safe_get(normalized)
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    title = clean_cell(soup.title.get_text(' ', strip=True)) if soup.title else ''
    text = clean_cell(soup.get_text(' ', strip=True))[:MAX_CONTEXT_CHARS]

    anchors: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in soup.find_all('a', href=True):
        href = _normalize_url(urljoin(normalized, str(node.get('href') or '')))
        if not href or href in seen or not _same_domain(href, normalized):
            continue
        label = clean_cell(node.get_text(' ', strip=True))[:160]
        if not label and node.find('img') and node.find('img').get('alt'):
            label = clean_cell(node.find('img').get('alt'))[:160]
        seen.add(href)
        anchors.append({'url': href, 'text': label})
        if len(anchors) >= MAX_ANCHORS:
            break

    jsonld: list[str] = []
    for script in soup.find_all('script', type='application/ld+json'):
        raw = clean_cell(script.string or script.get_text() or '')
        if raw:
            jsonld.append(raw[:8000])
        if len(jsonld) >= 12:
            break

    return AiPage(url=normalized, html=html[:MAX_CONTEXT_CHARS], text=text, title=title, anchors=anchors, jsonld=jsonld)


def _field_schema(contract: list[RequestedField]) -> list[dict[str, str | bool]]:
    return [
        {
            'column': field.original,
            'kind': field.kind,
            'required': field.required,
        }
        for field in contract
    ]


def _safe_json_loads(raw: str) -> dict:
    text = str(raw or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        text = text.replace('json\n', '', 1).replace('JSON\n', '', 1)
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _chat_json(system: str, user_payload: dict, max_tokens: int = 2500) -> dict:
    api_key = _secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key')
    if not api_key:
        return {}
    payload = {
        'model': _model_name(),
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'max_tokens': max_tokens,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=35,
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return _safe_json_loads(content)
    except Exception:
        return {}


def _discover_product_urls_with_ai(page: AiPage, max_products: int) -> list[str]:
    system = (
        'Você é o motor de descoberta de produtos de um sistema de importação Bling. '
        'Analise os links e o texto da página e selecione SOMENTE URLs que pareçam páginas reais de produto. '
        'Ignore login, carrinho, checkout, política, blog, contato, categoria sem produto e redes sociais. '
        'Responda apenas JSON.'
    )
    payload = {
        'page_url': page.url,
        'page_title': page.title,
        'anchors': page.anchors,
        'page_text_sample': page.text[:6000],
        'max_products': max_products,
        'expected_json': {'product_urls': ['https://...']},
    }
    parsed = _chat_json(system, payload, max_tokens=3500)
    urls = parsed.get('product_urls', [])
    if not isinstance(urls, list):
        return []
    result: list[str] = []
    for item in urls:
        normalized = _normalize_url(str(item or ''))
        if normalized and _same_domain(normalized, page.url) and normalized not in result:
            result.append(normalized)
        if len(result) >= max_products:
            break
    return result


def _default_columns_for_operation(operation: str) -> list[str]:
    if operation == 'estoque':
        return ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    return [
        'URL',
        'Código',
        'SKU',
        'GTIN',
        'Descrição',
        'Nome',
        'Preço',
        'Preço unitário (OBRIGATÓRIO)',
        'URL Imagens',
        'Imagens',
        'Marca',
        'Categoria',
    ]


def _extract_rows_with_ai(page: AiPage, contract: list[RequestedField], operation: str, max_rows: int) -> list[dict[str, str]]:
    columns = [field.original for field in contract]
    system = (
        'Você é um extrator AI Only para produtos de e-commerce e importação no Bling. '
        'Extraia SOMENTE as colunas solicitadas. Não invente dados. Se um campo não estiver claro, deixe vazio. '
        'Se houver vários produtos no texto/listagem, retorne várias linhas. Se for página de produto, retorne uma linha. '
        'Para estoque: sem estoque, esgotado ou indisponível deve ser 0. Para disponível sem quantidade, use 1. '
        'Para imagens: use URLs separadas por |. Para GTIN/EAN inválido, deixe vazio. Responda apenas JSON.'
    )
    payload = {
        'operation': operation,
        'page_url': page.url,
        'page_title': page.title,
        'requested_fields': _field_schema(contract),
        'required_output_columns_exactly': columns,
        'jsonld': page.jsonld,
        'anchors': page.anchors[:80],
        'page_text': page.text,
        'max_rows': max_rows,
        'expected_json': {'rows': [{column: '' for column in columns}]},
    }
    parsed = _chat_json(system, payload, max_tokens=4500)
    rows = parsed.get('rows', [])
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []

    clean_rows: list[dict[str, str]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue
        row: dict[str, str] = {}
        for field in contract:
            value = clean_cell(raw_row.get(field.original, ''))
            if field.kind == 'url' and not value:
                value = page.url
            if field.kind == 'gtin':
                value = clean_gtin(value)
            if field.kind == 'imagem':
                parts = [clean_cell(part) for part in re.split(r'[|,\n]+', value) if clean_cell(part)]
                value = '|'.join(dict.fromkeys([part for part in parts if part.startswith(('http://', 'https://'))]))
            if field.kind == 'estoque':
                key = normalize_key(value)
                if any(term in key for term in ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque']):
                    value = '0'
            row[field.original] = value
        if any(str(value or '').strip() for value in row.values()):
            clean_rows.append(row)
        if len(clean_rows) >= max_rows:
            break
    return clean_rows


def _unique_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        values = {normalize_key(key): str(value or '').strip() for key, value in row.items()}
        identity = values.get('url') or values.get('codigo') or values.get('sku') or values.get('gtin') or values.get('descricao') or '|'.join(values.values())
        key = normalize_key(identity)[:140]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def run_ai_only_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    all_products: bool = True,
    max_pages: int = 250,
    max_products: int = 1000,
    keep_only_requested_columns: bool = True,
) -> pd.DataFrame:
    """Busca por site usando IA como cérebro principal.

    O sistema baixa as páginas para dar contexto, mas a decisão de links de produtos e a
    extração dos campos ficam com a IA. Este motor não usa fallback determinístico para
    preencher dados de produto.
    """
    urls = split_urls(raw_urls)
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    if not columns:
        columns = _default_columns_for_operation(operation)
    contract = build_contract(columns)

    if not urls:
        return pd.DataFrame(columns=columns)
    if not ai_available():
        return pd.DataFrame(columns=columns)

    start_pages = [page for page in (_make_page(url) for url in urls[: max(1, min(len(urls), max_pages))]) if page is not None]
    if not start_pages:
        return pd.DataFrame(columns=columns)

    target_urls: list[str] = []
    if all_products:
        per_page_limit = max(1, min(max_products, 120))
        for page in start_pages:
            for discovered in _discover_product_urls_with_ai(page, per_page_limit):
                if discovered not in target_urls:
                    target_urls.append(discovered)
                if len(target_urls) >= max_products:
                    break
            if len(target_urls) >= max_products:
                break
    else:
        target_urls = [page.url for page in start_pages]

    if not target_urls:
        target_urls = [page.url for page in start_pages]

    rows: list[dict[str, str]] = []
    max_workers = max(1, min(MAX_WORKERS, len(target_urls)))
    max_rows_per_page = 20 if all_products else 5

    def _extract_url(url: str) -> list[dict[str, str]]:
        page = _make_page(url)
        if page is None:
            return []
        return _extract_rows_with_ai(page, contract, operation, max_rows=max_rows_per_page)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_extract_url, url) for url in target_urls[:max_products]]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception:
                continue
            if len(rows) >= max_products:
                break

    rows = _unique_rows(rows)[:max_products]
    df = pd.DataFrame(rows).fillna('')
    if keep_only_requested_columns:
        df = _ensure_columns(df, columns)
    return df.fillna('')
