from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import pandas as pd
import requests

from bling_app_zero.core.column_contract import RequestedField, build_contract

RESPONSIBLE_FILE = 'bling_app_zero/engines/site_operations/stoqui_api_engine.py'
STOQUI_REST_BASE = 'https://spb.stoqui.com.br/rest/v1'
STOQUI_PRODUCT_PATH = '/produto'
DEFAULT_TIMEOUT = 18
MAX_DISCOVERY_PAGES = 8
MAX_DISCOVERY_SCRIPTS = 28
UUID_RE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
JWT_RE = re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
STOQUI_PUBLIC_SIGNALS = (
    'stoqui',
    'spb.stoqui.com.br',
    'supabase',
    'produto_variacao',
    'produto_variacao_valor',
    '/rest/v1/produto',
)
RICH_PRODUCT_SELECT = '*,categoria!produto_categoria_id_fkey(nome),produto_variacao(*,produto_variacao_valor(atributo_valor(id,valor,destaque,atributos(id,nome))))'

DEFAULT_CADASTRO_COLUMNS = [
    'URL',
    'Código',
    'SKU',
    'GTIN',
    'Descrição',
    'Descrição complementar',
    'Preço unitário (OBRIGATÓRIO)',
    'URL Imagens',
    'Marca',
    'Categoria',
    'Estoque',
]
DEFAULT_ESTOQUE_COLUMNS = [
    'Código',
    'Descrição',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _split_raw_urls(raw_urls: str) -> list[str]:
    values = re.split(r'[\n,;\t ]+', str(raw_urls or '').strip())
    return [value.strip() for value in values if value.strip().startswith(('http://', 'https://'))]


def can_handle_stoqui_url(raw_urls: str) -> bool:
    # BLINGFIX: lojas Stoqui podem usar domínio próprio, como megacentereletronicos.com.br.
    # Antes o motor só rodava quando a URL continha stoqui.com.br; nesses domínios o
    # sistema caía no scraper genérico e encontrava HTML React vazio. Agora qualquer URL
    # pública pode passar por uma tentativa leve de descoberta; se não for Stoqui, a
    # execução retorna DataFrame vazio e o fluxo segue para o motor genérico.
    return bool(_split_raw_urls(raw_urls))


def _extract_user_ids_from_text(text: str) -> list[str]:
    found: list[str] = []
    raw = str(text or '')
    for pattern in (
        r'user_id\s*=\s*eq\.([0-9a-fA-F-]{36})',
        r'user_id=eq\.([0-9a-fA-F-]{36})',
        r'distinct_id=([0-9a-fA-F-]{36})',
        r'%24user_id=([0-9a-fA-F-]{36})',
        r'"user_id"\s*:\s*"([0-9a-fA-F-]{36})"',
        r"'user_id'\s*:\s*'([0-9a-fA-F-]{36})'",
        r'user_id["\']?\s*[:=]\s*["\']([0-9a-fA-F-]{36})["\']',
        r'usuario_id["\']?\s*[:=]\s*["\']([0-9a-fA-F-]{36})["\']',
        r'lojista_id["\']?\s*[:=]\s*["\']([0-9a-fA-F-]{36})["\']',
    ):
        for match in re.findall(pattern, raw, flags=re.IGNORECASE):
            if UUID_RE.fullmatch(match) and match not in found:
                found.append(match)
    for match in UUID_RE.findall(raw):
        if match not in found:
            found.append(match)
    return found


def _extract_user_ids_from_url(url: str) -> list[str]:
    parsed = urlparse(str(url or ''))
    query = parse_qs(parsed.query)
    joined_values = ' '.join(value for values in query.values() for value in values)
    return _extract_user_ids_from_text(f'{url} {joined_values}')


def _extract_anon_key(text: str) -> str:
    raw = str(text or '')
    for key in JWT_RE.findall(raw):
        if len(key) > 80:
            return key
    for pattern in (
        r'(?:anonKey|anon_key|SUPABASE_ANON_KEY|VITE_SUPABASE_ANON_KEY)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'(?:supabaseAnonKey|supabase_anon_key)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'apikey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    ):
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ''


def _http_get_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/javascript,text/javascript,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
            },
        )
        if response.status_code >= 400:
            return ''
        return response.text or ''
    except Exception:
        return ''


def _looks_like_stoqui_text(text: str) -> bool:
    raw = str(text or '').lower()
    return any(signal in raw for signal in STOQUI_PUBLIC_SIGNALS)


def _discover_from_public_pages(raw_urls: str) -> tuple[list[str], str, bool, str]:
    urls = _split_raw_urls(raw_urls)
    user_ids: list[str] = []
    anon_key = _extract_anon_key(raw_urls)
    visited_scripts: set[str] = set()
    saw_stoqui_signal = _looks_like_stoqui_text(raw_urls)
    public_root = ''

    for url in urls[:MAX_DISCOVERY_PAGES]:
        parsed = urlparse(url)
        if not public_root and parsed.scheme and parsed.netloc:
            public_root = f'{parsed.scheme}://{parsed.netloc}'
        for user_id in _extract_user_ids_from_url(url):
            if user_id not in user_ids:
                user_ids.append(user_id)
        html = _http_get_text(url)
        if not html:
            continue
        saw_stoqui_signal = saw_stoqui_signal or _looks_like_stoqui_text(html)
        for user_id in _extract_user_ids_from_text(html):
            if user_id not in user_ids:
                user_ids.append(user_id)
        if not anon_key:
            anon_key = _extract_anon_key(html)

        for src in SCRIPT_SRC_RE.findall(html)[:MAX_DISCOVERY_SCRIPTS]:
            script_url = urljoin(url, src)
            if script_url in visited_scripts:
                continue
            visited_scripts.add(script_url)
            script_text = _http_get_text(script_url)
            if not script_text:
                continue
            saw_stoqui_signal = saw_stoqui_signal or _looks_like_stoqui_text(script_text)
            for user_id in _extract_user_ids_from_text(script_text):
                if user_id not in user_ids:
                    user_ids.append(user_id)
            if not anon_key:
                anon_key = _extract_anon_key(script_text)
            has_public_api_credentials = bool(user_ids and anon_key)
            if has_public_api_credentials or saw_stoqui_signal:
                break
        has_public_api_credentials = bool(user_ids and anon_key)
        if has_public_api_credentials or (user_ids and saw_stoqui_signal):
            break

    return user_ids, anon_key, saw_stoqui_signal, public_root


def _headers(anon_key: str) -> dict[str, str]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; BlingSiteCrawler/1.0)',
        'Accept': 'application/json',
        'Origin': 'https://app.stoqui.com.br',
        'Referer': 'https://app.stoqui.com.br/',
    }
    if anon_key:
        headers['apikey'] = anon_key
        headers['Authorization'] = f'Bearer {anon_key}'
    return headers


def _request_products(user_id: str, anon_key: str) -> list[dict]:
    endpoint = f'{STOQUI_REST_BASE}{STOQUI_PRODUCT_PATH}'
    params = {
        'select': RICH_PRODUCT_SELECT,
        'user_id': f'eq.{user_id}',
        'deletado_em': 'is.null',
        'order': 'oculto.asc,destaque.desc,criado_em.desc,id.desc',
    }
    try:
        response = requests.get(endpoint, params=params, headers=_headers(anon_key), timeout=DEFAULT_TIMEOUT)
        if response.status_code in {401, 403} and anon_key:
            response = requests.get(endpoint, params=params, headers=_headers(''), timeout=DEFAULT_TIMEOUT)
        if response.status_code >= 400:
            return []
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _first_value(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() not in {'none', 'nan', 'null'}:
            return text
    return ''


def _deep_pick(data: dict, aliases: Iterable[str]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in data.items()}
    for alias in aliases:
        value = lowered.get(str(alias).strip().lower())
        if isinstance(value, (str, int, float)) and _first_value(value):
            return _first_value(value)
    for alias in aliases:
        needle = str(alias).strip().lower()
        for key, value in lowered.items():
            if needle in key and isinstance(value, (str, int, float)) and _first_value(value):
                return _first_value(value)
    return ''


def _money_value(data: dict) -> str:
    return _deep_pick(data, ('preco_venda', 'preco_promocional', 'preco', 'valor_venda', 'valor', 'price', 'preco_unitario'))


def _stock_value(data: dict) -> str:
    return _deep_pick(data, ('estoque', 'quantidade', 'saldo', 'qtd', 'stock', 'quantity', 'balanco', 'balanço'))


def _category_value(product: dict) -> str:
    category = product.get('categoria')
    if isinstance(category, dict):
        value = _deep_pick(category, ('nome', 'descricao', 'titulo', 'name'))
        if value:
            return value
    return _deep_pick(product, ('categoria_nome', 'nome_categoria', 'categoria', 'category'))


def _images_value(product: dict) -> str:
    candidates = []
    for key, value in product.items():
        key_text = str(key).lower()
        if not any(token in key_text for token in ('imagem', 'image', 'foto', 'photo', 'galeria', 'gallery')):
            continue
        if isinstance(value, str):
            candidates.extend(re.findall(r'https?://[^\s,"\']+', value))
            if value.startswith('/'):
                candidates.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    candidates.append(item)
                elif isinstance(item, dict):
                    candidates.append(_deep_pick(item, ('url', 'src', 'imagem', 'image', 'foto')))
        elif isinstance(value, dict):
            candidates.append(_deep_pick(value, ('url', 'src', 'imagem', 'image', 'foto')))
    clean: list[str] = []
    for item in candidates:
        text = str(item or '').strip()
        if not text:
            continue
        if text.startswith('//'):
            text = f'https:{text}'
        if text.startswith('/'):
            text = urljoin('https://spb.stoqui.com.br', text)
        if text not in clean:
            clean.append(text)
    return '|'.join(clean[:12])


def _variation_label(variation: dict) -> str:
    parts: list[str] = []
    for key in ('nome', 'descricao', 'titulo', 'sku', 'codigo'):
        value = _first_value(variation.get(key))
        if value and value not in parts:
            parts.append(value)
    values = variation.get('produto_variacao_valor')
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            attr = item.get('atributo_valor')
            if isinstance(attr, dict):
                attr_name = ''
                atributos = attr.get('atributos')
                if isinstance(atributos, dict):
                    attr_name = _deep_pick(atributos, ('nome', 'name'))
                attr_value = _deep_pick(attr, ('valor', 'nome', 'name'))
                label = f'{attr_name}: {attr_value}' if attr_name and attr_value else attr_value
                if label and label not in parts:
                    parts.append(label)
    return ' / '.join(parts)


def _public_product_url(product: dict, public_root: str) -> str:
    raw = _deep_pick(product, ('url', 'link', 'permalink'))
    if raw.startswith(('http://', 'https://')):
        return raw
    if raw.startswith('/') and public_root:
        return urljoin(public_root, raw)
    slug = _deep_pick(product, ('slug', 'url_slug', 'permalink_slug'))
    product_id = _first_value(product.get('id'))
    if public_root:
        if raw:
            return urljoin(public_root, raw)
        if slug and product_id:
            return f'{public_root.rstrip("/")}/produto/{product_id}-{slug.strip("/")}'
        if slug:
            return f'{public_root.rstrip("/")}/produto/{slug.strip("/")}'
        if product_id:
            return f'{public_root.rstrip("/")}/produto/{product_id}'
    return raw or slug or product_id


def _base_product_dict(product: dict, variation: dict | None = None, public_root: str = '') -> dict[str, str]:
    variation = variation or {}
    descricao = _first_value(
        _deep_pick(variation, ('nome', 'descricao', 'titulo', 'name')),
        _deep_pick(product, ('nome', 'titulo', 'descricao', 'name', 'produto')),
    )
    variation_text = _variation_label(variation)
    if variation_text and variation_text.lower() not in descricao.lower():
        descricao = f'{descricao} - {variation_text}' if descricao else variation_text

    codigo = _first_value(
        _deep_pick(variation, ('codigo', 'sku', 'referencia', 'id')),
        _deep_pick(product, ('codigo', 'sku', 'referencia', 'cod_produto', 'id')),
    )
    gtin = _first_value(
        _deep_pick(variation, ('gtin', 'ean', 'codigo_barras', 'cod_barras')),
        _deep_pick(product, ('gtin', 'ean', 'codigo_barras', 'cod_barras')),
    )
    return {
        'url': _public_product_url(product, public_root),
        'codigo': codigo or gtin,
        'id_produto': codigo or gtin or _first_value(product.get('id')),
        'sku': codigo,
        'gtin': gtin,
        'descricao': descricao,
        'descricao_complementar': _deep_pick(product, ('descricao_completa', 'descricao_complementar', 'detalhes', 'observacoes', 'observação')),
        'preco': _first_value(_money_value(variation), _money_value(product)),
        'estoque': _first_value(_stock_value(variation), _stock_value(product)),
        'imagem': _first_value(_images_value(variation), _images_value(product)),
        'marca': _deep_pick(product, ('marca', 'brand', 'fabricante')),
        'categoria': _category_value(product),
    }


def _flatten_products(products: list[dict], public_root: str = '') -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        variations = product.get('produto_variacao')
        if isinstance(variations, list) and variations:
            for variation in variations:
                if isinstance(variation, dict):
                    rows.append(_base_product_dict(product, variation, public_root))
        else:
            rows.append(_base_product_dict(product, public_root=public_root))
    return rows


def _value_for_field(row: dict[str, str], field: RequestedField) -> str:
    kind = field.kind
    original = str(field.original or '').strip()
    original_norm = re.sub(r'[^a-z0-9]+', '_', original.lower()).strip('_')
    if kind == 'url':
        return row.get('url', '')
    if kind in {'codigo', 'id_produto'}:
        return row.get('codigo') or row.get('id_produto', '')
    if kind == 'gtin':
        return row.get('gtin', '')
    if kind in {'descricao', 'descricao_curta', 'nome_apoio'}:
        return row.get('descricao', '')
    if kind in {'descricao_complementar', 'ficha_tecnica', 'caracteristicas'}:
        return row.get('descricao_complementar', '')
    if kind in {'preco_unitario', 'preco_custo'}:
        return row.get('preco', '')
    if kind == 'estoque':
        return row.get('estoque', '')
    if kind == 'imagem':
        return row.get('imagem', '')
    if kind == 'marca':
        return row.get('marca', '')
    if kind == 'categoria':
        return row.get('categoria', '')
    if original_norm in row:
        return row.get(original_norm, '')
    for key, value in row.items():
        if original_norm and original_norm in key:
            return value
    return ''


def _to_dataframe(rows: list[dict[str, str]], requested_columns: Iterable[str] | None, operation: str) -> pd.DataFrame:
    defaults = DEFAULT_ESTOQUE_COLUMNS if operation == 'estoque' else DEFAULT_CADASTRO_COLUMNS
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()] or defaults
    contract = build_contract(columns)
    output_rows = []
    for row in rows:
        output_rows.append({field.original: _value_for_field(row, field) for field in contract})
    df = pd.DataFrame(output_rows).fillna('')
    for column in columns:
        if column not in df.columns:
            df[column] = ''
    return df.loc[:, columns].fillna('')


def run_stoqui_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    max_products: int = 1_000_000,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    normalized_operation = 'estoque' if str(operation or '').strip().lower() == 'estoque' else 'cadastro'
    if not can_handle_stoqui_url(raw_urls):
        return pd.DataFrame()

    _emit(progress_callback, {
        'stage': 'API Stoqui',
        'message': 'Verificando se o site usa motor Stoqui/React e API interna de produtos...',
        'progress': 0.10,
        'responsible_file': RESPONSIBLE_FILE,
    })
    user_ids = _extract_user_ids_from_text(raw_urls)
    anon_key = _extract_anon_key(raw_urls)
    discovered_ids, discovered_key, saw_stoqui_signal, public_root = _discover_from_public_pages(raw_urls)
    for user_id in discovered_ids:
        if user_id not in user_ids:
            user_ids.append(user_id)
    if not anon_key:
        anon_key = discovered_key

    has_public_api_credentials = bool(user_ids and anon_key)
    if not user_ids or (not saw_stoqui_signal and not has_public_api_credentials):
        _emit(progress_callback, {
            'stage': 'API Stoqui',
            'message': 'Motor Stoqui/API pública não identificado nesta URL. Indo para o motor genérico.',
            'progress': 0.18,
            'responsible_file': RESPONSIBLE_FILE,
            'stoqui_signal': bool(saw_stoqui_signal),
            'has_public_api_credentials': bool(has_public_api_credentials),
            'user_ids_found': len(user_ids),
        })
        return pd.DataFrame()

    _emit(progress_callback, {
        'stage': 'API Stoqui',
        'message': f'Consultando API interna Stoqui para {len(user_ids)} possível(is) catálogo(s)...',
        'progress': 0.22,
        'stoqui_user_ids': len(user_ids),
        'has_anon_key': bool(anon_key),
        'stoqui_signal': bool(saw_stoqui_signal),
        'responsible_file': RESPONSIBLE_FILE,
    })

    products: list[dict] = []
    tried_ids = 0
    for user_id in user_ids:
        tried_ids += 1
        chunk = _request_products(user_id, anon_key)
        if chunk:
            products.extend(chunk)
        if len(products) >= int(max_products or 1_000_000):
            break
        if tried_ids >= 24 and not products:
            break

    if not products:
        _emit(progress_callback, {
            'stage': 'API Stoqui',
            'message': 'API Stoqui não retornou produtos. Indo para o motor genérico.',
            'progress': 0.30,
            'responsible_file': RESPONSIBLE_FILE,
            'stoqui_user_ids_tried': tried_ids,
        })
        return pd.DataFrame()

    rows = _flatten_products(products, public_root=public_root)[: int(max_products or 1_000_000)]
    df = _to_dataframe(rows, requested_columns, normalized_operation)
    _emit(progress_callback, {
        'stage': 'API Stoqui',
        'message': f'{len(df)} produto(s) carregados direto da API interna Stoqui.',
        'progress': 0.88,
        'rows': len(df),
        'columns': len(df.columns),
        'responsible_file': RESPONSIBLE_FILE,
    })
    return df


__all__ = ['can_handle_stoqui_url', 'run_stoqui_site_engine']
