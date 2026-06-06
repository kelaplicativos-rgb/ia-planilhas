from __future__ import annotations

import importlib
import re
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_autocadastro_api.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
SEND_TIMEOUT = 30
_FALLBACK_STATE: dict[str, Any] = {}

DEFAULT_CONDICAO = 'Novo'
DEFAULT_PRODUCAO = 'T'
DEFAULT_PESO = 0.300
DEFAULT_LARGURA = 11
DEFAULT_ALTURA = 2
DEFAULT_PROFUNDIDADE = 16
DEFAULT_VOLUMES = 1
DEFAULT_ITENS_CAIXA = 1
DEFAULT_LINK_VIDEO = ''

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'cod produto', 'cod'),
    'nome': ('nome', 'produto', 'título', 'titulo', 'nome produto', 'descrição produto', 'descricao produto'),
    'descricao': ('descrição', 'descricao', 'descrição curta', 'descricao curta', 'detalhes'),
    'descricao_complementar': ('descrição complementar', 'descricao complementar', 'complemento', 'descrição longa', 'descricao longa'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'valor', 'valor venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'gtin_tributario': ('gtin tributário', 'gtin tributario', 'gtin/ean tributário', 'gtin/ean tributario'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
    'quantidade': ('quantidade', 'saldo', 'estoque', 'balanço', 'balanco', 'qtd', 'qtde'),
    'deposito': ('depósito', 'deposito', 'nome depósito', 'nome deposito'),
    'categoria': ('categoria', 'categoria produto', 'categoria do produto'),
    'imagens': ('imagens', 'imagem', 'url imagem', 'url imagens', 'fotos'),
    'link_externo': ('link externo', 'url produto', 'url do produto', 'link produto', 'link real', 'url', 'origem url'),
    'link_video': ('link vídeo', 'link video', 'video', 'vídeo', 'url video', 'url vídeo'),
    'condicao': ('condição', 'condicao'),
    'producao': ('produção', 'producao'),
    'peso_liquido': ('peso líquido', 'peso liquido', 'peso'),
    'peso_bruto': ('peso bruto',),
    'largura': ('largura',),
    'altura': ('altura',),
    'profundidade': ('profundidade', 'comprimento'),
    'volumes': ('volumes', 'volume'),
    'itens_caixa': ('itens p/ caixa', 'itens por caixa', 'itens caixa', 'itens/caixa'),
}


@dataclass(frozen=True)
class AutoCadastroApiResult:
    attempted: int
    created: int
    stock_updated: int
    failed: int
    skipped: int
    errors: tuple[str, ...]
    failed_indices: tuple[int, ...] = ()


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def _state_store() -> MutableMapping[str, Any]:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def _secret(name: str, default: str = '') -> str:
    st = _streamlit_module()
    if st is not None:
        try:
            bling = st.secrets.get('bling', {})
            value = bling.get(name, default) if hasattr(bling, 'get') else default
            return str(value or default).strip()
        except Exception:
            pass
    return default


def _url(path: str) -> str:
    base = (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')
    if str(path or '').startswith(('http://', 'https://')):
        return str(path)
    return base + '/' + str(path or '').lstrip('/')


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in (('ã', 'a'), ('á', 'a'), ('à', 'a'), ('â', 'a'), ('é', 'e'), ('ê', 'e'), ('í', 'i'), ('ó', 'o'), ('ô', 'o'), ('õ', 'o'), ('ú', 'u'), ('ç', 'c')):
        text = text.replace(old, new)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _column_map(columns: Iterable[object]) -> dict[str, str]:
    normalized = {_normalize_column_name(column): str(column) for column in columns}
    out: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            column = normalized.get(_normalize_column_name(alias))
            if column:
                out[field] = column
                break
    return out


def _value(row: pd.Series, mapping: dict[str, str], field: str, default: str = '') -> str:
    column = mapping.get(field)
    if not column:
        return default
    value = row.get(column, default)
    if pd.isna(value):
        return default
    return str(value or default).strip()


def _first_value(row: pd.Series, mapping: dict[str, str], fields: tuple[str, ...], default: str = '') -> str:
    for field in fields:
        value = _value(row, mapping, field)
        if value:
            return value
    return default


def _float_or_none(value: object) -> float | None:
    try:
        text = str(value or '').replace('R$', '').replace(' ', '').strip()
        if ',' in text and '.' in text:
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '.')
        return float(text) if text else None
    except Exception:
        return None


def _float_or_default(value: object, default: float) -> float:
    number = _float_or_none(value)
    return float(default if number is None else number)


def _int_or_default(value: object, default: int) -> int:
    number = _float_or_none(value)
    return int(default if number is None else number)


def _digits_only(value: object) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _api_number(value: float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number


def _clean(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if value in ('', None, {}):
            continue
        if isinstance(value, dict):
            nested = _clean(value)
            if nested:
                clean[key] = nested
        elif isinstance(value, list):
            items = [item for item in value if item not in ('', None, {})]
            if items:
                clean[key] = items
        else:
            clean[key] = value
    return clean


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


def _valid_gtin(value: object) -> str:
    digits = _digits_only(value)
    return digits if len(digits) in {8, 12, 13, 14} else ''


def _identity_engine(row: pd.Series, mapping: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    codigo = _value(row, mapping, 'codigo') or _value(row, mapping, 'gtin')
    nome = _value(row, mapping, 'nome') or _value(row, mapping, 'descricao') or codigo
    if not nome:
        return None, 'falta nome/descrição/código para cadastrar produto.'
    if not codigo:
        codigo = nome[:60]
    payload: dict[str, Any] = {'nome': str(nome)[:120], 'codigo': str(codigo)[:120], 'tipo': 'P', 'situacao': 'A'}
    gtin = _valid_gtin(_value(row, mapping, 'gtin'))
    if gtin:
        payload['gtin'] = gtin
        payload['tributacao'] = {'gtin': _valid_gtin(_value(row, mapping, 'gtin_tributario')) or gtin}
    return payload, ''


def _description_engine(row: pd.Series, mapping: dict[str, str], fallback_name: str) -> dict[str, Any]:
    descricao = _first_value(row, mapping, ('descricao', 'descricao_complementar'), fallback_name)
    return {'descricaoCurta': descricao, 'descricaoComplementar': ''}


def _price_engine(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    preco = _float_or_none(_value(row, mapping, 'preco'))
    return {'preco': preco} if preco is not None else {}


def _defaults_engine(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    producao_raw = str(_value(row, mapping, 'producao') or '').strip().lower()
    condicao_raw = str(_value(row, mapping, 'condicao') or '').strip().lower()
    return {
        'condicao': 'Usado' if condicao_raw in {'usado', 'usada', 'u'} else DEFAULT_CONDICAO,
        'producao': 'P' if producao_raw in {'propria', 'própria', 'p'} else DEFAULT_PRODUCAO,
        'unidade': _value(row, mapping, 'unidade', 'UN') or 'UN',
        'pesoLiquido': _api_number(_float_or_default(_value(row, mapping, 'peso_liquido'), DEFAULT_PESO)),
        'pesoBruto': _api_number(_float_or_default(_value(row, mapping, 'peso_bruto'), DEFAULT_PESO)),
        'dimensoes': {
            'largura': _api_number(_float_or_default(_value(row, mapping, 'largura'), DEFAULT_LARGURA)),
            'altura': _api_number(_float_or_default(_value(row, mapping, 'altura'), DEFAULT_ALTURA)),
            'profundidade': _api_number(_float_or_default(_value(row, mapping, 'profundidade'), DEFAULT_PROFUNDIDADE)),
        },
        'volumes': _int_or_default(_value(row, mapping, 'volumes'), DEFAULT_VOLUMES),
        'itensPorCaixa': _int_or_default(_value(row, mapping, 'itens_caixa'), DEFAULT_ITENS_CAIXA),
    }


def _taxonomy_engine(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {'marca': _value(row, mapping, 'marca')}
    categoria = _value(row, mapping, 'categoria')
    if categoria:
        payload['categoria'] = {'descricao': categoria}
    return payload


def _media_engine(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    payload = {'linkExterno': _value(row, mapping, 'link_externo'), 'linkVideo': _value(row, mapping, 'link_video', DEFAULT_LINK_VIDEO)}
    imagens = _value(row, mapping, 'imagens')
    if imagens:
        urls = [u.strip() for u in re.split(r'[|,;\n]+', imagens) if u.strip().lower().startswith(('http://', 'https://'))]
        if urls:
            payload['midia'] = {'imagens': [{'link': url} for url in urls[:10]]}
    return payload


def _tax_engine(row: pd.Series, mapping: dict[str, str], current_payload: dict[str, Any]) -> dict[str, Any]:
    tributacao = dict(current_payload.get('tributacao') or {})
    ncm = _digits_only(_value(row, mapping, 'ncm'))
    if ncm:
        tributacao['ncm'] = ncm
    return {'tributacao': tributacao} if tributacao else {}


def _validate_payload(payload: dict[str, Any]) -> str:
    if not str(payload.get('nome') or '').strip():
        return 'payload sem nome.'
    if not str(payload.get('codigo') or '').strip():
        return 'payload sem código/SKU.'
    return ''


def _product_payload(row: pd.Series, mapping: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    identity, reason = _identity_engine(row, mapping)
    if identity is None:
        return None, reason
    payload: dict[str, Any] = {}
    payload.update(identity)
    payload.update(_defaults_engine(row, mapping))
    payload.update(_description_engine(row, mapping, str(payload.get('nome') or '')))
    payload.update(_price_engine(row, mapping))
    payload.update(_taxonomy_engine(row, mapping))
    payload.update(_media_engine(row, mapping))
    payload.update(_tax_engine(row, mapping, payload))
    clean = _clean(payload)
    validation_error = _validate_payload(clean)
    if validation_error:
        return None, validation_error
    return clean, ''


def _deposit_id(token: dict[str, Any], row: pd.Series, mapping: dict[str, str]) -> str:
    store = _state_store()
    current = str(store.get(API_STOCK_DEPOSIT_ID_KEY) or _secret('stock_deposit_id', '') or '').strip()
    if current:
        return current
    wanted = str(_value(row, mapping, 'deposito') or store.get(API_STOCK_DEPOSIT_KEY) or _secret('stock_deposit_name', _secret('default_stock_deposit_name', '')) or '').strip().lower()
    for path in ('/estoques/depositos', '/depositos', '/estoque/depositos'):
        try:
            response = requests.get(_url(path), headers={'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}, timeout=20)
            if response.status_code >= 400:
                continue
            payload = response.json()
            items = payload.get('data') or payload.get('dados') or payload.get('items') or [] if isinstance(payload, dict) else []
            if isinstance(items, dict):
                items = [items]
            for item in items if isinstance(items, list) else []:
                nested = item.get('deposito') if isinstance(item.get('deposito'), dict) else {}
                item_id = str(item.get('id') or item.get('idDeposito') or nested.get('id') or '').strip()
                name = str(item.get('descricao') or item.get('nome') or nested.get('descricao') or nested.get('nome') or '').strip()
                if item_id and (not wanted or wanted == item_id.lower() or wanted == name.lower()):
                    store[API_STOCK_DEPOSIT_ID_KEY] = item_id
                    return item_id
        except Exception:
            continue
    return ''


def _create_product(token: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str]:
    path = _secret('product_create_path', '/produtos') or '/produtos'
    try:
        response = requests.post(_url(path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
        if response.status_code >= 400:
            return '', f'Cadastro recusado ({response.status_code}): {str(response.text or "")[:220]}'
        product_id = _extract_product_id(response.json())
        if not product_id:
            return '', 'Cadastro aceito, mas a API não retornou o ID do produto.'
        return product_id, ''
    except Exception as exc:
        return '', f'Falha técnica no cadastro: {exc}'


def _update_stock(token: dict[str, Any], product_id: str, deposit_id: str, quantity: float) -> str:
    payload = {'produto': {'id': str(product_id)}, 'deposito': {'id': str(deposit_id)}, 'operacao': 'B', 'quantidade': _api_number(quantity)}
    last_error = ''
    for path in ('/estoques', '/estoques/saldos'):
        try:
            response = requests.post(_url(path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
            if response.status_code < 400:
                return ''
            last_error = f'Estoque recusado ({response.status_code}) em {path}: {str(response.text or "")[:220]}'
        except Exception as exc:
            last_error = f'Falha técnica no estoque: {exc}'
    return last_error or 'Falha ao atualizar estoque.'


def autocadastrar_e_atualizar_estoque(df: pd.DataFrame, *, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> AutoCadastroApiResult:
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return AutoCadastroApiResult(0, 0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado.',))
    if not isinstance(df, pd.DataFrame) or df.empty:
        return AutoCadastroApiResult(0, 0, 0, 0, 0, ('Nenhum produto para autocadastrar.',))
    work = df.copy().fillna('')
    if 'autocadastro_elegivel' in work.columns:
        eligible = work[work['autocadastro_elegivel'].astype(str).str.upper().eq('SIM')].copy()
        if not eligible.empty:
            work = eligible
    mapping = _column_map(work.columns)
    total = len(work)
    created = stock_updated = failed = skipped = 0
    errors: list[str] = []
    failed_indices: list[int] = []
    for position, (index, row) in enumerate(work.iterrows(), start=1):
        if progress_callback:
            progress_callback({'stage': 'AutoCadastro via API', 'processed': position - 1, 'total': total, 'created': created, 'stock_updated': stock_updated, 'failed': failed, 'skipped': skipped, 'progress': (position - 1) / max(total, 1)})
        product_payload, reason = _product_payload(row, mapping)
        if product_payload is None:
            skipped += 1
            failed_indices.append(int(index) if isinstance(index, int) else position - 1)
            if len(errors) < 12:
                errors.append(f'Linha {int(index)+1 if isinstance(index, int) else position}: {reason}')
            continue
        product_id, create_error = _create_product(token, product_payload)
        if not product_id:
            failed += 1
            failed_indices.append(int(index) if isinstance(index, int) else position - 1)
            if len(errors) < 12:
                errors.append(f'Linha {int(index)+1 if isinstance(index, int) else position}: {create_error}')
            continue
        created += 1
        quantity = _float_or_none(_value(row, mapping, 'quantidade'))
        deposit_id = _deposit_id(token, row, mapping)
        if quantity is None or not deposit_id:
            skipped += 1
            if len(errors) < 12:
                errors.append(f'Linha {int(index)+1 if isinstance(index, int) else position}: produto cadastrado ID {product_id}, mas estoque não atualizado por falta de quantidade/depósito.')
            continue
        stock_error = _update_stock(token, product_id, deposit_id, quantity)
        if stock_error:
            failed += 1
            failed_indices.append(int(index) if isinstance(index, int) else position - 1)
            if len(errors) < 12:
                errors.append(f'Linha {int(index)+1 if isinstance(index, int) else position}: produto cadastrado ID {product_id}, mas estoque falhou: {stock_error}')
        else:
            stock_updated += 1
    if progress_callback:
        progress_callback({'stage': 'AutoCadastro concluído', 'processed': total, 'total': total, 'created': created, 'stock_updated': stock_updated, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    result = AutoCadastroApiResult(total, created, stock_updated, failed, skipped, tuple(errors), tuple(sorted(set(failed_indices))))
    add_audit_event('blingsmartcore_autocadastro_api_finished', area='AUTOCADASTRO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': result.attempted, 'created': result.created, 'stock_updated': result.stock_updated, 'failed': result.failed, 'skipped': result.skipped, 'responsible_file': RESPONSIBLE_FILE})
    return result


__all__ = ['AutoCadastroApiResult', 'autocadastrar_e_atualizar_estoque']
