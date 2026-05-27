from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    normalize_operation,
    operation_label,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id', 'id produto', 'id_produto', 'idproduto', 'codigo bling', 'código bling'),
    'codigo': ('codigo', 'código', 'sku', 'ref', 'referencia', 'referência'),
    'nome': ('nome', 'descrição', 'descricao', 'produto', 'título', 'titulo'),
    'descricao': ('descricao complementar', 'descrição complementar', 'descricao curta', 'descrição curta', 'descrição do produto', 'descricao do produto'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
    'quantidade': ('quantidade', 'saldo', 'estoque', 'balanço', 'balanco', 'qtd'),
    'deposito': ('deposito', 'depósito', 'nome deposito', 'nome depósito'),
}


@dataclass(frozen=True)
class DirectSendResult:
    attempted: int
    sent: int
    failed: int
    skipped: int
    errors: tuple[str, ...]


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    text = re.sub(r'\s+', ' ', text)
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


def _int_or_none(value: str) -> int | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return int(number)


def _token() -> tuple[dict[str, Any] | None, str]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, str(meta.get('store_mode') or '')
    return token, str(meta.get('store_mode') or '')


def is_direct_send_available() -> bool:
    token, _mode = _token()
    return isinstance(token, dict) and bool(token.get('access_token'))


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {token.get('access_token')}",
    }


def _endpoint_for(operation: str, row_id: str = '') -> tuple[str, str]:
    operation = normalize_operation(operation)
    if operation == OP_CADASTRO:
        return 'POST', _secret('product_create_path', '/produtos') or '/produtos'
    if operation == OP_ATUALIZACAO_PRECO:
        path = _secret('price_update_path', '/produtos/{id}') or '/produtos/{id}'
        return _secret('price_update_method', 'PATCH').upper() or 'PATCH', path.replace('{id}', row_id)
    if operation == OP_ESTOQUE:
        path = _secret('stock_write_path', '/estoques/saldos') or '/estoques/saldos'
        method = _secret('stock_update_method', 'POST').upper() or 'POST'
        return method, path.replace('{id}', row_id).replace('{idProduto}', row_id)
    return 'POST', _secret('product_create_path', '/produtos') or '/produtos'


def _url(path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return api_base_url() + '/' + path.lstrip('/')


def _payload_cadastro(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    preco = _float_or_none(_value(row, mapping, 'preco'))
    payload: dict[str, Any] = {
        'nome': _value(row, mapping, 'nome') or _value(row, mapping, 'codigo') or 'Produto sem nome',
        'codigo': _value(row, mapping, 'codigo'),
        'tipo': 'P',
        'situacao': 'A',
        'descricaoCurta': _value(row, mapping, 'descricao'),
        'gtin': _value(row, mapping, 'gtin'),
        'marca': _value(row, mapping, 'marca'),
        'unidade': _value(row, mapping, 'unidade', 'UN') or 'UN',
        'tributacao': {},
    }
    if preco is not None:
        payload['preco'] = preco
    ncm = _value(row, mapping, 'ncm')
    if ncm:
        payload['tributacao']['ncm'] = ncm
    payload = {key: value for key, value in payload.items() if value not in ('', None, {})}
    return payload


def _payload_preco(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any] | None:
    preco = _float_or_none(_value(row, mapping, 'preco'))
    if preco is None:
        return None
    return {'preco': preco}


def _payload_estoque(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any] | None:
    quantidade = _float_or_none(_value(row, mapping, 'quantidade'))
    if quantidade is None:
        return None
    payload: dict[str, Any] = {
        'saldo': quantidade,
        'quantidade': quantidade,
    }
    produto_id = _value(row, mapping, 'id')
    codigo = _value(row, mapping, 'codigo')
    deposito = _value(row, mapping, 'deposito')
    if produto_id:
        payload['produto'] = {'id': produto_id}
    elif codigo:
        payload['produto'] = {'codigo': codigo}
    if deposito:
        payload['deposito'] = {'nome': deposito}
    return payload


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
        return payload, ''
    return None, f'Operação sem envio direto configurado: {operation_label(operation)}.'


def send_dataframe_to_bling(df: pd.DataFrame, operation: str, *, limit: int | None = None) -> DirectSendResult:
    operation = normalize_operation(operation)
    token, store_mode = _token()
    if not isinstance(token, dict):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado. Conecte o app antes de enviar direto.',))

    if not isinstance(df, pd.DataFrame) or df.empty:
        return DirectSendResult(0, 0, 0, 0, ('Planilha final vazia.',))

    mapping = _column_map(df.columns)
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    sent = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    for index, row in rows.iterrows():
        row_id = _value(row, mapping, 'id')
        payload, skip_reason = _payload_for(operation, row, mapping)
        if payload is None:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {index + 1}: {skip_reason}')
            continue

        method, path = _endpoint_for(operation, row_id)
        try:
            response = requests.request(method, _url(path), headers=_headers(token), json=payload, timeout=30)
            if response.status_code >= 400:
                failed += 1
                preview = response.text[:240]
                if len(errors) < 8:
                    errors.append(f'Linha {index + 1}: status {response.status_code} · {preview}')
                continue
            sent += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {index + 1}: {exc}')

    result = DirectSendResult(attempted=len(rows), sent=sent, failed=failed, skipped=skipped, errors=tuple(errors))
    add_audit_event(
        'bling_direct_flow_send_finished',
        area='BLING_ENVIO',
        status='OK' if result.failed == 0 else 'PARCIAL',
        details={
            'operation': operation,
            'attempted': result.attempted,
            'sent': result.sent,
            'failed': result.failed,
            'skipped': result.skipped,
            'store_mode': store_mode,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return result


__all__ = ['DirectSendResult', 'is_direct_send_available', 'send_dataframe_to_bling']
