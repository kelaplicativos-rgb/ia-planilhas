from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import clear_token, load_token
from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    normalize_operation,
    operation_label,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
PRODUCT_LOOKUP_CACHE_KEY = 'bling_product_lookup_cache_by_code_v1'

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id produto', 'id_produto', 'idproduto', 'id', 'codigo bling', 'código bling'),
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto'),
    'nome': ('nome', 'produto', 'título', 'titulo', 'nome produto', 'nome do produto', 'descrição produto', 'descricao produto'),
    'descricao': ('descrição', 'descricao', 'descrição curta', 'descricao curta', 'descrição do produto', 'descricao do produto', 'descricao complementar', 'descrição complementar', 'detalhes', 'observação', 'observacao'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda', 'preço de venda', 'preco de venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
    'quantidade': ('quantidade', 'saldo', 'estoque', 'balanço', 'balanco', 'qtd', 'qtde'),
    'deposito': ('depósito', 'deposito', 'nome depósito', 'nome deposito', 'depósito padrão', 'deposito padrao'),
    'categoria': ('categoria', 'categoria produto', 'categoria do produto'),
    'imagens': ('imagens', 'imagem', 'url imagem', 'url imagens', 'fotos'),
}


@dataclass(frozen=True)
class DirectSendResult:
    attempted: int
    sent: int
    failed: int
    skipped: int
    errors: tuple[str, ...]
    not_found_indices: tuple[int, ...] = ()


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _stock_deposit_name() -> str:
    session_value = str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or '').strip()
    if session_value:
        return session_value
    return _secret('stock_deposit_name', _secret('default_stock_deposit_name', '')).strip()


def _stock_deposit_id() -> str:
    return str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or _secret('stock_deposit_id', '')).strip()


def _looks_like_local_path(value: str) -> bool:
    text = str(value or '').strip().replace('\\', '/')
    if not text:
        return False
    lowered = text.lower()
    return lowered.startswith(('data/', './data/', '../data/')) or lowered.endswith(('.json', '.sqlite', '.sqlite3', '.db'))


def _api_path_secret(name: str, default: str) -> str:
    value = _secret(name, default) or default
    if _looks_like_local_path(value):
        add_audit_event(
            'bling_direct_invalid_api_path_secret_ignored',
            area='BLING_ENVIO',
            status='CORRIGIDO',
            details={'secret_name': name, 'configured_value': value, 'fallback_value': default, 'reason': 'Campo de endpoint da API recebeu caminho local/arquivo. Usando endpoint padrão do Bling.', 'responsible_file': RESPONSIBLE_FILE},
        )
        return default
    return value


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e')
    text = text.replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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


def _number_text(value: str) -> str:
    text = str(value or '').strip().replace('R$', '').replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    return text


def _float_or_none(value: str) -> float | None:
    try:
        text = _number_text(value)
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _digits_only(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _is_ean_like(value: object) -> bool:
    digits = _digits_only(value)
    return len(digits) in {8, 12, 13, 14}


def _looks_like_bling_internal_id(value: object) -> bool:
    text = str(value or '').strip()
    digits = _digits_only(text)
    if not text or not digits or digits != text:
        return False
    if _is_ean_like(digits):
        return False
    return 1 <= len(digits) <= 11


def _stock_product_reference(row: pd.Series, mapping: dict[str, str]) -> dict[str, str]:
    produto_id = _value(row, mapping, 'id')
    codigo = _value(row, mapping, 'codigo')
    gtin = _value(row, mapping, 'gtin')

    if _looks_like_bling_internal_id(produto_id):
        return {'id': produto_id}
    if codigo:
        return {'codigo': codigo}
    if gtin:
        return {'codigo': gtin}
    if produto_id:
        return {'codigo': produto_id}
    return {}


def _token() -> tuple[dict[str, Any] | None, str]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, str(meta.get('store_mode') or '')
    return token, str(meta.get('store_mode') or '')


def is_direct_send_available() -> bool:
    token, _mode = _token()
    return isinstance(token, dict) and bool(token.get('access_token'))


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _endpoint_for(operation: str, row_id: str = '') -> tuple[str, str]:
    operation = normalize_operation(operation)
    if operation == OP_CADASTRO:
        return 'POST', _api_path_secret('product_create_path', '/produtos') or '/produtos'
    if operation == OP_ATUALIZACAO_PRECO:
        path = _api_path_secret('price_update_path', '/produtos/{id}') or '/produtos/{id}'
        return _secret('price_update_method', 'PATCH').upper() or 'PATCH', path.replace('{id}', row_id)
    if operation == OP_ESTOQUE:
        path = _api_path_secret('stock_write_path', '/estoques/saldos') or '/estoques/saldos'
        method = _secret('stock_update_method', 'POST').upper() or 'POST'
        return method, path.replace('{id}', row_id).replace('{idProduto}', row_id)
    return 'POST', _api_path_secret('product_create_path', '/produtos') or '/produtos'


def _url(path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return api_base_url() + '/' + path.lstrip('/')


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if value in ('', None, {}):
            continue
        if isinstance(value, dict):
            nested = {nested_key: nested_value for nested_key, nested_value in value.items() if nested_value not in ('', None, {})}
            if nested:
                clean[key] = nested
            continue
        clean[key] = value
    return clean


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
    return []


def _lookup_cache() -> dict[str, str]:
    cache = st.session_state.get(PRODUCT_LOOKUP_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[PRODUCT_LOOKUP_CACHE_KEY] = cache
    return cache


def _resolve_product_id_by_code(token: dict[str, Any], code: str) -> str:
    code = str(code or '').strip()
    if not code:
        return ''
    cache = _lookup_cache()
    cache_key = code.lower()
    if cache_key in cache:
        return str(cache.get(cache_key) or '')

    lookup_path = _api_path_secret('product_lookup_path', '/produtos') or '/produtos'
    candidates = ({'codigo': code}, {'criterio': code}, {'pesquisa': code})
    for params in candidates:
        try:
            response = requests.get(_url(lookup_path), headers=_headers(token), params=params, timeout=20)
            if response.status_code in {401, 403}:
                response.raise_for_status()
            if response.status_code >= 400:
                continue
            for item in _extract_items(response.json()):
                item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                item_code = str(item.get('codigo') or item.get('sku') or item.get('codigoProduto') or '').strip()
                if item_id and (not item_code or item_code.lower() == code.lower() or params != {'codigo': code}):
                    cache[cache_key] = item_id
                    add_audit_event('bling_product_lookup_resolved', area='BLING_ENVIO', status='OK', details={'code': code, 'product_id': item_id, 'params': params, 'responsible_file': RESPONSIBLE_FILE})
                    return item_id
        except Exception as exc:
            add_audit_event('bling_product_lookup_failed', area='BLING_ENVIO', status='AVISO', details={'code': code, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
            break
    cache[cache_key] = ''
    return ''


def _resolve_stock_payload_product(token: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    produto = payload.get('produto')
    if not isinstance(produto, dict):
        return None, 'Produto ausente no payload de estoque.'
    produto_id = str(produto.get('id') or '').strip()
    if produto_id and _looks_like_bling_internal_id(produto_id):
        payload['produto'] = {'id': produto_id}
        return payload, ''
    code = str(produto.get('codigo') or produto.get('gtin') or produto_id or '').strip()
    resolved_id = _resolve_product_id_by_code(token, code)
    if resolved_id:
        payload['produto'] = {'id': resolved_id}
        return payload, ''
    return None, f'Produto não encontrado no Bling pelo código/SKU/GTIN: {code or "vazio"}. Cadastre o produto antes de atualizar saldo.'


def _api_error_message(index: object, response: requests.Response) -> str:
    status = int(response.status_code)
    preview = str(response.text or '')[:240]
    line = int(index) + 1 if isinstance(index, int) else index
    if status in {401, 403}:
        return f'Linha {line}: Bling recusou a autorização ({status}). O token pode ter expirado ou o app não tem permissão para esta operação. Desconecte o Bling, conecte novamente e tente enviar de novo.'
    if status == 404:
        return f'Linha {line}: produto não encontrado no Bling (404). Separe esta linha para cadastro antes de atualizar estoque/preço. {preview}'
    if status == 422:
        return f'Linha {line}: dados recusados pelo Bling (422). Revise campos obrigatórios e formato. {preview}'
    return f'Linha {line}: status {status} · {preview}'


def _payload_cadastro(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    preco = _float_or_none(_value(row, mapping, 'preco'))
    payload: dict[str, Any] = {'nome': _value(row, mapping, 'nome') or _value(row, mapping, 'codigo') or 'Produto sem nome', 'codigo': _value(row, mapping, 'codigo'), 'tipo': 'P', 'situacao': 'A', 'descricaoCurta': _value(row, mapping, 'descricao'), 'gtin': _value(row, mapping, 'gtin'), 'marca': _value(row, mapping, 'marca'), 'unidade': _value(row, mapping, 'unidade', 'UN') or 'UN', 'tributacao': {}}
    if preco is not None:
        payload['preco'] = preco
    ncm = _value(row, mapping, 'ncm')
    if ncm:
        payload['tributacao']['ncm'] = ncm
    categoria = _value(row, mapping, 'categoria')
    if categoria:
        payload['categoria'] = {'descricao': categoria}
    imagens = _value(row, mapping, 'imagens')
    if imagens:
        urls = [url.strip() for url in re.split(r'[|,;\n]+', imagens) if url.strip()]
        if urls:
            payload['midia'] = {'imagens': [{'link': url} for url in urls[:10]]}
    return _clean_payload(payload)


def _payload_preco(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any] | None:
    preco = _float_or_none(_value(row, mapping, 'preco'))
    if preco is None:
        return None
    return {'preco': preco}


def _payload_estoque(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any] | None:
    quantidade = _float_or_none(_value(row, mapping, 'quantidade'))
    if quantidade is None:
        return None
    payload: dict[str, Any] = {'saldo': quantidade, 'quantidade': quantidade}
    produto = _stock_product_reference(row, mapping)
    deposito_id = _stock_deposit_id()
    deposito_nome = _value(row, mapping, 'deposito') or _stock_deposit_name()
    if produto:
        payload['produto'] = produto
    if deposito_id:
        payload['deposito'] = {'id': deposito_id}
    elif deposito_nome:
        payload['deposito'] = {'nome': deposito_nome}
    return _clean_payload(payload)


def _payload_for(operation: str, row: pd.Series, mapping: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    operation = normalize_operation(operation)
    if operation == OP_CADASTRO:
        return _payload_cadastro(row, mapping), ''
    if operation == OP_ATUALIZACAO_PRECO:
        row_id = _value(row, mapping, 'id')
        if not row_id:
            return None, 'Atualização de preço exige coluna com ID do produto no Bling.'
        payload = _payload_preco(row, mapping)
        return payload, '' if payload else 'Preço ausente ou inválido.'
    if operation == OP_ESTOQUE:
        payload = _payload_estoque(row, mapping)
        if payload is None:
            return None, 'Quantidade/saldo ausente ou inválido.'
        if not payload.get('produto'):
            return None, 'Estoque exige ID real do produto no Bling, código/SKU ou GTIN/EAN.'
        if not payload.get('deposito'):
            return None, 'Busque e selecione o depósito do Bling antes de atualizar estoque.'
        return payload, ''
    return None, f'Operação sem envio direto configurado: {operation_label(operation)}.'


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    operation = normalize_operation(operation)
    mapping = _column_map(df.columns)
    previews: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        payload, reason = _payload_for(operation, row, mapping)
        previews.append({'payload': payload or {}, 'status': 'OK' if payload else 'IGNORADO', 'motivo': reason})
    return previews


def send_dataframe_to_bling(df: pd.DataFrame, operation: str, *, limit: int | None = None) -> DirectSendResult:
    operation = normalize_operation(operation)
    token, store_mode = _token()
    if not isinstance(token, dict):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado. Conecte o app antes de enviar direto.',))
    if not isinstance(df, pd.DataFrame) or df.empty:
        return DirectSendResult(0, 0, 0, 0, ('Planilha final vazia.',))

    mapping = _column_map(df.columns)
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    sent = failed = skipped = 0
    errors: list[str] = []
    not_found_indices: list[int] = []
    auth_failed = False

    for index, row in rows.iterrows():
        row_id = _value(row, mapping, 'id')
        if operation == OP_ESTOQUE and not _looks_like_bling_internal_id(row_id):
            row_id = ''
        payload, skip_reason = _payload_for(operation, row, mapping)
        if payload is None:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {index + 1}: {skip_reason}')
            continue

        if operation == OP_ESTOQUE:
            payload, resolve_reason = _resolve_stock_payload_product(token, payload)
            if payload is None:
                failed += 1
                try:
                    not_found_indices.append(int(index))
                except Exception:
                    pass
                if len(errors) < 8:
                    errors.append(f'Linha {index + 1}: {resolve_reason}')
                continue

        method, path = _endpoint_for(operation, row_id)
        try:
            response = requests.request(method, _url(path), headers=_headers(token), json=payload, timeout=30)
            if response.status_code >= 400:
                failed += 1
                if response.status_code == 404:
                    try:
                        not_found_indices.append(int(index))
                    except Exception:
                        pass
                if response.status_code in {401, 403}:
                    auth_failed = True
                if len(errors) < 8:
                    errors.append(_api_error_message(index, response))
                if auth_failed:
                    break
                continue
            sent += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {index + 1}: {exc}')

    if auth_failed:
        try:
            clear_token()
        except Exception:
            pass
        skipped += max(0, len(rows) - sent - failed - skipped)
        add_audit_event('bling_direct_flow_auth_failed_token_cleared', area='BLING_ENVIO', status='ERRO', details={'operation': operation, 'store_mode': store_mode, 'responsible_file': RESPONSIBLE_FILE})

    result = DirectSendResult(attempted=len(rows), sent=sent, failed=failed, skipped=skipped, errors=tuple(errors), not_found_indices=tuple(not_found_indices))
    add_audit_event(
        'bling_direct_flow_send_finished',
        area='BLING_ENVIO',
        status='OK' if result.failed == 0 else 'PARCIAL',
        details={'operation': operation, 'attempted': result.attempted, 'sent': result.sent, 'failed': result.failed, 'skipped': result.skipped, 'not_found_count': len(result.not_found_indices), 'store_mode': store_mode, 'stock_deposit_id': _stock_deposit_id() if operation == OP_ESTOQUE else None, 'stock_deposit_configured': bool(_stock_deposit_id() or _stock_deposit_name()) if operation == OP_ESTOQUE else None, 'responsible_file': RESPONSIBLE_FILE},
    )
    return result


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']