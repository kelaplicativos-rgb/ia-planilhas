from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core import bling_direct_sender as raw_sender
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_price_sender_guarded.py'


def _product_store_price_payloads(product_store_id: str, product_id: str, channel_id: str, price: float, field: str) -> list[tuple[str, str, str, dict[str, Any]]]:
    price_value = raw_sender._api_number(price)
    path = raw_sender._store_update_path(product_store_id)
    method = (raw_sender._secret('product_store_update_method', 'PUT') or 'PUT').upper()
    product_store_id = str(product_store_id)
    product_id = str(product_id)
    channel_id = str(channel_id)

    payloads: list[tuple[str, dict[str, Any]]] = [
        ('produto_loja_idProdutoLoja_preco', {'idProdutoLoja': product_store_id, field: price_value}),
        (
            'produto_loja_ids_planos_preco',
            {
                'id': product_store_id,
                'idProdutoLoja': product_store_id,
                'idProduto': product_id,
                'idLoja': channel_id,
                field: price_value,
            },
        ),
        (
            'produto_loja_objetos_com_idProdutoLoja_preco',
            {
                'idProdutoLoja': product_store_id,
                'produto': {'id': product_id},
                'loja': {'id': channel_id},
                field: price_value,
            },
        ),
        ('produto_loja_preco_minimo_legado_seguro', {field: price_value}),
    ]
    attempts = [(method, path, label, payload) for label, payload in payloads]
    if method not in {'PATCH', 'PUT'}:
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco', {'idProdutoLoja': product_store_id, field: price_value}))
    elif method != 'PUT':
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco', {'idProdutoLoja': product_store_id, field: price_value}))
    return raw_sender._dedupe_price_attempts(attempts)


def _install_price_payload_guard() -> None:
    raw_sender._product_store_price_payloads = _product_store_price_payloads
    add_audit_event(
        'bling_price_sender_guard_installed',
        area='BLING_ENVIO',
        status='OK',
        details={
            'reason': 'Atualizacao por canal envia idProdutoLoja no payload antes do fallback minimo.',
            'legacy_price_paths_blocked': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    _install_price_payload_guard()
    return raw_sender.preview_payloads(df, OP_ATUALIZACAO_PRECO, limit=limit)


def send_dataframe_to_bling_price(
    df: pd.DataFrame,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
):
    _install_price_payload_guard()
    return raw_sender.send_dataframe_to_bling(
        df,
        OP_ATUALIZACAO_PRECO,
        limit=limit,
        progress_callback=progress_callback,
    )


__all__ = ['preview_payloads', 'send_dataframe_to_bling_price']
