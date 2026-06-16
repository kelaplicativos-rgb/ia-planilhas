from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core import bling_direct_sender as raw_sender
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_price_sender_guarded.py'


def _store_price_values(price_value: int | float, field: str) -> dict[str, Any]:
    values = {'preco': price_value, 'precoPromocional': price_value}
    if field not in values:
        values[field] = price_value
    return values


def _product_store_price_payloads(product_store_id: str, product_id: str, channel_id: str, price: float, field: str) -> list[tuple[str, str, str, dict[str, Any]]]:
    price_value = raw_sender._api_number(price)
    price_values = _store_price_values(price_value, field)
    path = raw_sender._store_update_path(product_store_id)
    method = (raw_sender._secret('product_store_update_method', 'PUT') or 'PUT').upper()
    product_store_id = str(product_store_id)
    product_id = str(product_id)
    channel_id = str(channel_id)

    payloads: list[tuple[str, dict[str, Any]]] = [
        ('produto_loja_idProdutoLoja_preco_promocional', {'idProdutoLoja': product_store_id, **price_values}),
        (
            'produto_loja_ids_planos_preco_promocional',
            {
                'id': product_store_id,
                'idProdutoLoja': product_store_id,
                'idProduto': product_id,
                'idLoja': channel_id,
                **price_values,
            },
        ),
        (
            'produto_loja_objetos_com_idProdutoLoja_preco_promocional',
            {
                'idProdutoLoja': product_store_id,
                'produto': {'id': product_id},
                'loja': {'id': channel_id},
                **price_values,
            },
        ),
        ('produto_loja_preco_promocional_legado_seguro', dict(price_values)),
    ]
    attempts = [(method, path, label, payload) for label, payload in payloads]
    if method not in {'PATCH', 'PUT'}:
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco_promocional', {'idProdutoLoja': product_store_id, **price_values}))
    elif method != 'PUT':
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco_promocional', {'idProdutoLoja': product_store_id, **price_values}))
    return raw_sender._dedupe_price_attempts(attempts)


def _install_price_payload_guard() -> None:
    raw_sender._product_store_price_payloads = _product_store_price_payloads
    add_audit_event(
        'bling_price_sender_guard_installed',
        area='BLING_ENVIO',
        status='OK',
        details={
            'reason': 'Atualizacao por canal envia idProdutoLoja com preco e precoPromocional no payload.',
            'legacy_price_paths_blocked': True,
            'store_price_fields': ['preco', 'precoPromocional'],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _emit(progress_callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _safe_int_attr(obj: object, name: str, default: int = 0) -> int:
    try:
        return int(getattr(obj, name) or 0)
    except Exception:
        return int(default or 0)


def _safe_tuple_attr(obj: object, name: str) -> tuple[Any, ...]:
    try:
        value = getattr(obj, name)
    except Exception:
        return tuple()
    if value is None:
        return tuple()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _price_channel_separation(df: pd.DataFrame, *, limit: int | None = None) -> tuple[pd.DataFrame, list[int], list[str], dict[str, Any]]:
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = raw_sender._column_map(rows.columns)
    token, _mode = raw_sender._token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return rows.reset_index(drop=True), [], [], {'separation_enabled': False, 'reason': 'bling_not_connected', 'send_positions': list(range(len(rows)))}

    send_positions: list[int] = []
    missing_positions: list[int] = []
    errors: list[str] = []
    missing_details: list[dict[str, str]] = []

    for position, (_index, row) in enumerate(rows.iterrows()):
        channel_id = raw_sender._id_text(raw_sender._value(row, mapping, 'channel_id'))
        target = raw_sender._value(row, mapping, 'price_target')
        if not channel_id and 'canal' not in raw_sender._norm(target):
            send_positions.append(position)
            continue

        product_id = ''
        for candidate in raw_sender._row_candidates(row, mapping):
            product_id = raw_sender._resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if not product_id:
            missing_positions.append(position)
            errors.append(f'Linha {position + 1}: produto não encontrado no Bling por ID/Código/SKU/GTIN.')
            missing_details.append({'line': str(position + 1), 'product_id': '', 'channel_id': channel_id, 'reason': 'produto_nao_encontrado'})
            continue

        if channel_id:
            product_store_id = raw_sender._resolve_product_store_link_id(token, product_id, channel_id, row, mapping)
            if not product_store_id:
                channel_name = raw_sender._value(row, mapping, 'channel_name')
                label = f' ({channel_name})' if channel_name else ''
                missing_positions.append(position)
                errors.append(f'Linha {position + 1}: produto ID {product_id} não encontrado no canal {channel_id}{label}.')
                missing_details.append({'line': str(position + 1), 'product_id': product_id, 'channel_id': channel_id, 'channel_name': channel_name, 'reason': 'produto_sem_vinculo_no_canal'})
                continue

        send_positions.append(position)

    send_df = rows.iloc[send_positions].copy().reset_index(drop=True) if send_positions else pd.DataFrame(columns=list(rows.columns))
    diagnostics = {
        'separation_enabled': True,
        'total_rows': len(rows),
        'sendable_rows': len(send_positions),
        'missing_channel_rows': len(missing_positions),
        'send_positions': send_positions,
        'missing_details': missing_details[:30],
    }
    return send_df, missing_positions, errors, diagnostics


def preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    _install_price_payload_guard()
    return raw_sender.preview_payloads(df, OP_ATUALIZACAO_PRECO, limit=limit)


def send_dataframe_to_bling_price(
    df: pd.DataFrame,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    _install_price_payload_guard()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return raw_sender.send_dataframe_to_bling(
            df,
            OP_ATUALIZACAO_PRECO,
            limit=limit,
            progress_callback=progress_callback,
        )

    send_df, missing_positions, missing_errors, diagnostics = _price_channel_separation(df, limit=limit)
    if missing_positions:
        add_audit_event(
            'bling_price_channel_missing_rows_separated',
            area='BLING_ENVIO',
            status='PENDENCIA',
            details={**diagnostics, 'responsible_file': RESPONSIBLE_FILE},
        )
        _emit(
            progress_callback,
            {
                'stage': 'Separando produtos não encontrados no canal',
                'operation': OP_ATUALIZACAO_PRECO,
                'processed': 0,
                'total': len(df),
                'sent': 0,
                'failed': len(missing_positions),
                'skipped': 0,
                'progress': 0.03,
                'detail': f'{len(missing_positions)} produto(s) sem vínculo no canal foram separados como pendência.',
            },
        )

    if send_df.empty:
        attempted = len(df.fillna('').head(limit) if limit else df)
        return DirectSendResult(
            attempted,
            0,
            len(missing_positions),
            0,
            tuple(missing_errors[:80]),
            tuple(sorted(set(missing_positions))),
        )

    result = raw_sender.send_dataframe_to_bling(
        send_df,
        OP_ATUALIZACAO_PRECO,
        limit=None,
        progress_callback=progress_callback,
    )
    attempted = _safe_int_attr(result, 'attempted', len(send_df)) + len(missing_positions)
    sent = _safe_int_attr(result, 'sent')
    failed = _safe_int_attr(result, 'failed') + len(missing_positions)
    skipped = _safe_int_attr(result, 'skipped')
    errors = list(_safe_tuple_attr(result, 'errors')) + missing_errors

    send_positions = [int(item) for item in list(diagnostics.get('send_positions') or []) if str(item).lstrip('-').isdigit()]
    raw_not_found = []
    for item in _safe_tuple_attr(result, 'not_found_indices'):
        try:
            raw_index = int(item)
            raw_not_found.append(send_positions[raw_index] if 0 <= raw_index < len(send_positions) else raw_index)
        except Exception:
            continue
    not_found = sorted(set(raw_not_found + missing_positions))
    return DirectSendResult(attempted, sent, failed, skipped, tuple(errors[:80]), tuple(not_found))


__all__ = ['preview_payloads', 'send_dataframe_to_bling_price']
