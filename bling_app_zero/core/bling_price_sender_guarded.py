from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import requests

from bling_app_zero.core import bling_direct_sender as raw_sender
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_price_sender_guarded.py'
CHANNEL_ID_COLUMN = 'Bling canal venda id'
DEFAULT_CHANNEL_LOOKUP_PATHS = ('/lojas', '/lojas/vendas', '/canais-venda', '/canaisVenda', '/marketplaces')


def _store_price_values(price_value: int | float, field: str) -> dict[str, Any]:
    return {'preco': price_value, 'precoPromocional': price_value}


def _product_store_price_payloads(product_store_id: str, product_id: str, channel_id: str, price: float, field: str) -> list[tuple[str, str, str, dict[str, Any]]]:
    price_value = raw_sender._api_number(price)
    price_values = _store_price_values(price_value, field)
    path = raw_sender._store_update_path(product_store_id)
    method = (raw_sender._secret('product_store_update_method', 'PUT') or 'PUT').upper()
    product_store_id = str(product_store_id)
    product_id = str(product_id)
    channel_id = str(channel_id)

    payloads: list[tuple[str, dict[str, Any]]] = [
        ('produto_loja_idProdutoLoja_preco_e_promocional', {'idProdutoLoja': product_store_id, **price_values}),
        (
            'produto_loja_ids_planos_preco_e_promocional',
            {
                'id': product_store_id,
                'idProdutoLoja': product_store_id,
                'idProduto': product_id,
                'idLoja': channel_id,
                **price_values,
            },
        ),
        (
            'produto_loja_objetos_com_idProdutoLoja_preco_e_promocional',
            {
                'idProdutoLoja': product_store_id,
                'produto': {'id': product_id},
                'loja': {'id': channel_id},
                **price_values,
            },
        ),
        ('produto_loja_preco_e_promocional_legado_seguro', dict(price_values)),
    ]
    attempts = [(method, path, label, payload) for label, payload in payloads]
    if method not in {'PATCH', 'PUT'}:
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco_e_promocional', {'idProdutoLoja': product_store_id, **price_values}))
    elif method != 'PUT':
        attempts.insert(0, ('PUT', path, 'produto_loja_idProdutoLoja_preco_e_promocional', {'idProdutoLoja': product_store_id, **price_values}))
    return raw_sender._dedupe_price_attempts(attempts)


def _channel_lookup_paths() -> tuple[str, ...]:
    configured = raw_sender._secret('channel_lookup_paths', '') or raw_sender._secret('store_lookup_paths', '')
    if configured:
        paths = [part.strip() for part in configured.replace('\n', ';').replace(',', ';').split(';') if part.strip()]
        if paths:
            return tuple(paths)
    return DEFAULT_CHANNEL_LOOKUP_PATHS


def _item_channel_ids(item: dict[str, Any]) -> list[str]:
    return raw_sender._unique_non_empty([
        item.get('id'), item.get('idLoja'), item.get('idLojaVirtual'), item.get('lojaId'), item.get('idCanalVenda'), item.get('idMarketplace'),
        raw_sender._nested(item, 'loja', 'id'), raw_sender._nested(item, 'lojaVirtual', 'id'), raw_sender._nested(item, 'canalVenda', 'id'), raw_sender._nested(item, 'marketplace', 'id'),
    ])


def _item_channel_names(item: dict[str, Any]) -> list[str]:
    values = [
        item.get('nome'), item.get('descricao'), item.get('descrição'), item.get('nomeLoja'), item.get('nomeLojaVirtual'),
        item.get('apelido'), item.get('canal'), item.get('marketplace'), item.get('tipoIntegracao'),
        raw_sender._nested(item, 'loja', 'nome'), raw_sender._nested(item, 'lojaVirtual', 'nome'), raw_sender._nested(item, 'canalVenda', 'nome'), raw_sender._nested(item, 'marketplace', 'nome'),
    ]
    out: list[str] = []
    for value in values:
        text = str(value or '').strip()
        if text and text not in out:
            out.append(text)
    return out


def _name_matches(wanted: str, names: list[str]) -> bool:
    target = raw_sender._norm(wanted)
    if not target:
        return False
    for name in names:
        current = raw_sender._norm(name)
        if current and (current == target or current in target or target in current):
            return True
    return False


def _resolve_channel_id_by_name(token: dict[str, Any], channel_name: str) -> str:
    channel_name = str(channel_name or '').strip()
    if not channel_name:
        return ''
    cache = raw_sender._session_cache('bling_direct_price_channel_name_cache_v1')
    cache_key = raw_sender._norm(channel_name)
    if cache_key in cache:
        return str(cache.get(cache_key) or '')

    attempts: list[dict[str, Any]] = []
    params_variants = ({}, {'nome': channel_name}, {'pesquisa': channel_name}, {'criterio': channel_name})
    for path in _channel_lookup_paths():
        for params in params_variants:
            try:
                response = requests.get(raw_sender._url(path), headers=raw_sender._headers(token), params=params or None, timeout=raw_sender.PRICE_LOOKUP_TIMEOUT)
                attempts.append({'method': 'GET', 'path': path, 'params': params, 'status': int(response.status_code), 'response_preview': str(response.text or '')[:220]})
                if response.status_code in {401, 403}:
                    break
                if response.status_code >= 400:
                    continue
                for item in raw_sender._extract_items(raw_sender._safe_json(response)):
                    names = _item_channel_names(item)
                    ids = _item_channel_ids(item)
                    if ids and _name_matches(channel_name, names):
                        cache[cache_key] = ids[0]
                        add_audit_event(
                            'bling_price_channel_id_resolved_by_name',
                            area='BLING_ENVIO',
                            status='OK',
                            details={'channel_name': channel_name, 'channel_id': ids[0], 'path': path, 'names': names[:8], 'responsible_file': RESPONSIBLE_FILE},
                        )
                        return ids[0]
            except Exception as exc:
                attempts.append({'method': 'GET', 'path': path, 'params': params, 'status': 'EXCEPTION', 'error': str(exc)[:180]})
                break
    cache[cache_key] = ''
    add_audit_event(
        'bling_price_channel_id_not_resolved_by_name',
        area='BLING_ENVIO',
        status='AVISO',
        details={'channel_name': channel_name, 'paths': list(_channel_lookup_paths()), 'attempts': attempts[-8:], 'responsible_file': RESPONSIBLE_FILE},
    )
    return ''


def _ensure_channel_id_column(rows: pd.DataFrame, mapping: dict[str, str]) -> str:
    column = mapping.get('channel_id')
    if column and column in rows.columns:
        return column
    if CHANNEL_ID_COLUMN not in rows.columns:
        rows[CHANNEL_ID_COLUMN] = ''
    mapping['channel_id'] = CHANNEL_ID_COLUMN
    return CHANNEL_ID_COLUMN


def _guarded_price_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    mapping = raw_sender._column_map(df.columns)
    previews: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        price = raw_sender._number_value(raw_sender._value(row, mapping, 'preco'))
        channel_id = raw_sender._id_text(raw_sender._value(row, mapping, 'channel_id'))
        channel_name = raw_sender._value(row, mapping, 'channel_name')
        target = raw_sender._value(row, mapping, 'price_target') or ('Canal de venda' if channel_id or channel_name else 'Preço geral')
        if price is None:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Preço ausente ou inválido.'})
            continue
        price_value = raw_sender._api_number(price)
        if channel_id or channel_name:
            payload = {'preco': price_value, 'precoPromocional': price_value}
            endpoint = raw_sender.PRODUCT_STORE_UPDATE_PATH_TEMPLATE
            name_note = f' | Loja/canal por nome: {channel_name}' if channel_name and not channel_id else ''
            reason = f'Destino: {target} | Canal selecionado: atualiza Preço e Preço promocional do anúncio da loja.{name_note}'
        else:
            field = raw_sender._price_field_from_target(target)
            payload = {field: price_value}
            endpoint = '/produtos/{id}'
            reason = f'Destino: {target} | Sem canal selecionado: atualiza o preço geral do produto.'
        previews.append({'payload': payload, 'status': 'OK', 'motivo': f'{reason} | Endpoint seguro: {endpoint}'})
    return previews


def price_channel_targets(df: pd.DataFrame, *, limit: int = 300) -> dict[str, Any]:
    """Resumo leve para UI: mostra para qual loja/canal a atualização de preço vai mirar."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {'operation': OP_ATUALIZACAO_PRECO, 'total_rows': 0, 'targets': [], 'general_price_rows': 0, 'unresolved_channel_rows': 0}
    rows = df.fillna('').head(limit).copy()
    mapping = raw_sender._column_map(rows.columns)
    token, _mode = raw_sender._token()
    token_ok = isinstance(token, dict) and bool(token.get('access_token'))
    targets: dict[str, dict[str, Any]] = {}
    general_rows = 0
    unresolved_rows = 0
    resolved_by_name = 0
    for _position, (_index, row) in enumerate(rows.iterrows(), start=1):
        channel_id = raw_sender._id_text(raw_sender._value(row, mapping, 'channel_id'))
        channel_name = raw_sender._value(row, mapping, 'channel_name')
        target = raw_sender._value(row, mapping, 'price_target')
        wants_channel = bool(channel_id or channel_name or 'canal' in raw_sender._norm(target) or 'loja' in raw_sender._norm(target) or 'marketplace' in raw_sender._norm(target))
        if not wants_channel:
            general_rows += 1
            continue
        if not channel_id and channel_name and token_ok:
            channel_id = _resolve_channel_id_by_name(token, channel_name)
            if channel_id:
                resolved_by_name += 1
        if not channel_id and not channel_name:
            unresolved_rows += 1
            continue
        key = channel_id or raw_sender._norm(channel_name) or 'loja_sem_id'
        entry = targets.setdefault(
            key,
            {
                'channel_id': channel_id,
                'channel_name': channel_name or 'Loja/canal informado sem nome',
                'rows': 0,
                'resolved_by_name': bool(channel_id and channel_name),
                'api_target': raw_sender.PRODUCT_STORE_UPDATE_PATH_TEMPLATE,
                'fields': ['preco', 'precoPromocional'],
            },
        )
        if channel_id and not entry.get('channel_id'):
            entry['channel_id'] = channel_id
        if channel_name and (not entry.get('channel_name') or entry.get('channel_name') == 'Loja/canal informado sem nome'):
            entry['channel_name'] = channel_name
        entry['rows'] = int(entry.get('rows') or 0) + 1
    out_targets = sorted(targets.values(), key=lambda item: (-int(item.get('rows') or 0), str(item.get('channel_name') or '')))
    return {
        'operation': OP_ATUALIZACAO_PRECO,
        'total_rows': int(len(df)),
        'sampled_rows': int(len(rows)),
        'targets': out_targets,
        'general_price_rows': int(general_rows),
        'unresolved_channel_rows': int(unresolved_rows),
        'resolved_by_name': int(resolved_by_name),
        'token_available': bool(token_ok),
        'responsible_file': RESPONSIBLE_FILE,
    }


def _install_price_payload_guard() -> None:
    raw_sender._product_store_price_payloads = _product_store_price_payloads
    raw_sender._price_preview_payloads = _guarded_price_preview_payloads
    add_audit_event(
        'bling_price_sender_guard_installed',
        area='BLING_ENVIO',
        status='OK',
        details={
            'reason': 'Com canal selecionado, atualizacao mira o vinculo produto-loja e envia preco e precoPromocional. Sem canal, o fluxo normal atualiza o preco geral do produto.',
            'legacy_price_paths_blocked': True,
            'store_price_fields': ['preco', 'precoPromocional'],
            'preview_guarded': True,
            'auto_channel_lookup_by_name': True,
            'channel_lookup_paths': list(_channel_lookup_paths()),
            'ui_target_summary': True,
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
    rows = (df.fillna('').head(limit) if limit else df.fillna('')).copy()
    mapping = raw_sender._column_map(rows.columns)
    token, _mode = raw_sender._token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return rows.reset_index(drop=True), [], [], {'separation_enabled': False, 'reason': 'bling_not_connected', 'send_positions': list(range(len(rows)))}

    send_positions: list[int] = []
    missing_positions: list[int] = []
    errors: list[str] = []
    missing_details: list[dict[str, str]] = []
    resolved_channels = 0

    for position, (index, row) in enumerate(rows.iterrows()):
        channel_id = raw_sender._id_text(raw_sender._value(row, mapping, 'channel_id'))
        channel_name = raw_sender._value(row, mapping, 'channel_name')
        target = raw_sender._value(row, mapping, 'price_target')
        wants_channel = bool(channel_id or channel_name or 'canal' in raw_sender._norm(target) or 'loja' in raw_sender._norm(target) or 'marketplace' in raw_sender._norm(target))

        if wants_channel and not channel_id and channel_name:
            channel_id = _resolve_channel_id_by_name(token, channel_name)
            if channel_id:
                channel_column = _ensure_channel_id_column(rows, mapping)
                rows.at[index, channel_column] = channel_id
                resolved_channels += 1
                row = rows.loc[index]

        if not wants_channel:
            send_positions.append(position)
            continue
        if not channel_id:
            missing_positions.append(position)
            label = f' ({channel_name})' if channel_name else ''
            errors.append(f'Linha {position + 1}: canal/loja{label} não encontrado no Bling para atualização multiloja.')
            missing_details.append({'line': str(position + 1), 'product_id': '', 'channel_id': '', 'channel_name': channel_name, 'reason': 'loja_nao_encontrada_por_nome'})
            continue

        product_id = ''
        for candidate in raw_sender._row_candidates(row, mapping):
            product_id = raw_sender._resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if not product_id:
            missing_positions.append(position)
            errors.append(f'Linha {position + 1}: produto não encontrado no Bling por ID/Código/SKU/GTIN.')
            missing_details.append({'line': str(position + 1), 'product_id': '', 'channel_id': channel_id, 'channel_name': channel_name, 'reason': 'produto_nao_encontrado'})
            continue

        product_store_id = raw_sender._resolve_product_store_link_id(token, product_id, channel_id, row, mapping)
        if not product_store_id:
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
        'resolved_channels_by_name': resolved_channels,
        'send_positions': send_positions,
        'missing_details': missing_details[:30],
    }
    return send_df, missing_positions, errors, diagnostics


def preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    _install_price_payload_guard()
    return _guarded_price_preview_payloads(df, limit=limit)


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


__all__ = ['preview_payloads', 'price_channel_targets', 'send_dataframe_to_bling_price']
