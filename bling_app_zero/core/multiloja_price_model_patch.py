from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/multiloja_price_model_patch.py'
TARGET_MODULES = {
    'bling_app_zero.core.bling_direct_sender',
    'bling_app_zero.core.bling_price_sender_guarded',
}


def _audit(module: ModuleType, event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        module.add_audit_event(event, area='BLING_ENVIO', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _extend_aliases(current: tuple[str, ...], *new_values: str) -> tuple[str, ...]:
    out = list(current or tuple())
    seen = {str(item).strip().lower() for item in out}
    for value in new_values:
        text = str(value or '').strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def patch_direct_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_multiloja_model_aliases_patched', False):
        return
    aliases = getattr(module, 'PRICE_COLUMN_ALIASES', None)
    if not isinstance(aliases, dict):
        return
    aliases['id'] = _extend_aliases(aliases.get('id', tuple()), 'IdProduto', 'idproduto', 'id produto multilojas')
    aliases['codigo'] = _extend_aliases(aliases.get('codigo', tuple()), 'ID na Loja', 'id na loja')
    aliases['channel_name'] = _extend_aliases(aliases.get('channel_name', tuple()), 'Nome Loja (Multilojas)', 'nome loja multilojas', 'loja multilojas')
    aliases['preco_promocional'] = _extend_aliases(aliases.get('preco_promocional', tuple()), 'Preco Promocional', 'Preço Promocional', 'preco promocional', 'valor promocional')
    module._mapeiaai_multiloja_model_aliases_patched = True
    _audit(module, 'multiloja_price_model_aliases_installed', details={'aliases': ['IdProduto', 'ID na Loja', 'Nome Loja (Multilojas)', 'Preco Promocional']})


def _price_values(raw_sender: ModuleType, row: Any, mapping: dict[str, str]) -> tuple[float | None, float | None]:
    price = raw_sender._number_value(raw_sender._value(row, mapping, 'preco'))
    promo = raw_sender._number_value(raw_sender._value(row, mapping, 'preco_promocional'))
    if promo is None:
        promo = price
    return price, promo


def _store_attempts(raw_sender: ModuleType, product_store_id: str, product_id: str, channel_id: str, price: float, promo: float | None) -> list[tuple[str, str, str, dict[str, Any]]]:
    price_value = raw_sender._api_number(price)
    promo_value = raw_sender._api_number(promo if promo is not None else price)
    values = {'preco': price_value, 'precoPromocional': promo_value}
    path = raw_sender._store_update_path(product_store_id)
    method = (raw_sender._secret('product_store_update_method', 'PUT') or 'PUT').upper()
    payloads = [
        ('produto_loja_preco_multiloja_modelo_bling', {'idProdutoLoja': str(product_store_id), **values}),
        ('produto_loja_ids_multiloja_modelo_bling', {'id': str(product_store_id), 'idProdutoLoja': str(product_store_id), 'idProduto': str(product_id), 'idLoja': str(channel_id), **values}),
        ('produto_loja_objeto_multiloja_modelo_bling', {'idProdutoLoja': str(product_store_id), 'produto': {'id': str(product_id)}, 'loja': {'id': str(channel_id)}, **values}),
        ('produto_loja_preco_promocional_minimo', dict(values)),
    ]
    attempts = [(method, path, label, payload) for label, payload in payloads]
    if method != 'PUT':
        attempts.insert(0, ('PUT', path, 'produto_loja_preco_multiloja_modelo_bling', {'idProdutoLoja': str(product_store_id), **values}))
    return raw_sender._dedupe_price_attempts(attempts)


def _general_attempts(raw_sender: ModuleType, product_id: str, price: float, promo: float | None) -> list[tuple[str, str, str, dict[str, Any]]]:
    values = {'preco': raw_sender._api_number(price)}
    if promo is not None:
        values['precoPromocional'] = raw_sender._api_number(promo)
    configured_path = raw_sender._configured_path_or_default('price_update_path', '', 'multiloja_price_general_update_path_legacy_ignored')
    configured_method = (raw_sender._secret('price_update_method', 'PATCH') or 'PATCH').upper()
    attempts: list[tuple[str, str, str, dict[str, Any]]] = []
    for raw_path in raw_sender._unique_non_empty([configured_path, f'/produtos/{product_id}']):
        path = str(raw_path or '').replace('{idProduto}', str(product_id)).replace('{id}', str(product_id)).strip()
        method = configured_method if raw_path == configured_path else 'PATCH'
        attempts.append((method, path, 'produto_preco_e_promocional_multiloja_modelo', dict(values)))
        if method != 'PUT':
            attempts.append(('PUT', path, 'produto_preco_e_promocional_multiloja_modelo', dict(values)))
    return raw_sender._dedupe_price_attempts(attempts)


def patch_price_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_multiloja_model_sender_patched', False):
        return
    original = module.send_dataframe_to_bling_price
    raw_sender = module.raw_sender
    patch_direct_sender(raw_sender)

    def send_dataframe_to_bling_price_multiloja(df, *, limit=None, progress_callback=None):
        module._install_price_payload_guard()
        if not hasattr(df, 'columns') or df.empty:
            return original(df, limit=limit, progress_callback=progress_callback)
        rows = df.fillna('').head(limit) if limit else df.fillna('')
        mapping = raw_sender._column_map(rows.columns)
        has_multiloja_model = bool(mapping.get('preco_promocional') and mapping.get('channel_name'))
        if not has_multiloja_model:
            return original(df, limit=limit, progress_callback=progress_callback)
        token, _mode = raw_sender._token()
        if not isinstance(token, dict) or not token.get('access_token'):
            return raw_sender.DirectSendResult(0, 0, 0, len(rows), ('Bling não conectado. Conecte o app antes de atualizar preços.',), tuple())
        sent = failed = skipped = 0
        errors: list[str] = []
        not_found: list[int] = []
        for position, (index, row) in enumerate(rows.iterrows(), start=1):
            line = int(index) + 1 if isinstance(index, int) else position
            price, promo = _price_values(raw_sender, row, mapping)
            if price is None or price < 0:
                skipped += 1
                if len(errors) < 8:
                    errors.append(f'Linha {line}: preço ausente ou inválido.')
                continue
            product_id = ''
            for candidate in raw_sender._row_candidates(row, mapping):
                product_id = raw_sender._resolve_product_by_candidate(token, candidate)
                if product_id:
                    break
            if not product_id:
                failed += 1
                not_found.append(int(index) if isinstance(index, int) else position - 1)
                if len(errors) < 8:
                    errors.append(f'Linha {line}: produto não encontrado no Bling por IdProduto/Código/ID na Loja.')
                continue
            channel_id = raw_sender._id_text(raw_sender._value(row, mapping, 'channel_id'))
            channel_name = raw_sender._value(row, mapping, 'channel_name')
            if not channel_id and channel_name:
                channel_id = module._resolve_channel_id_by_name(token, channel_name)
            product_store_id = raw_sender._resolve_product_store_link_id(token, product_id, channel_id, row, mapping) if channel_id else ''
            if channel_id and not product_store_id:
                failed += 1
                if len(errors) < 8:
                    errors.append(f'Linha {line}: vínculo produto-loja não encontrado para {channel_name or channel_id}.')
                continue
            attempts = _store_attempts(raw_sender, product_store_id, product_id, channel_id, price, promo) if channel_id else _general_attempts(raw_sender, product_id, price, promo)
            ok, last_response, attempts_log = raw_sender._send_price_attempts(token, attempts)
            if ok:
                sent += 1
            else:
                failed += 1
                status = getattr(last_response, 'status_code', 'sem resposta')
                preview = str(getattr(last_response, 'text', '') or '')[:240]
                if len(errors) < 8:
                    errors.append(f'Linha {line}: Bling recusou preço multiloja ({status}). {preview}')
                _audit(module, 'multiloja_price_model_update_failed', status='AVISO', details={'line': line, 'product_id': product_id, 'channel_name': channel_name, 'channel_id': channel_id, 'product_store_id': product_store_id, 'attempts': attempts_log[-4:]})
        _audit(module, 'multiloja_price_model_sender_used', details={'rows': len(rows), 'sent': sent, 'failed': failed, 'skipped': skipped, 'rule': 'Preco e Preco Promocional enviados separadamente no vínculo produto-loja'})
        return raw_sender.DirectSendResult(len(rows), sent, failed, skipped, tuple(errors[:80]), tuple(not_found))

    module.send_dataframe_to_bling_price = send_dataframe_to_bling_price_multiloja
    module._mapeiaai_multiloja_model_sender_patched = True
    _audit(module, 'multiloja_price_model_sender_installed', details={'model_columns': ['IdProduto', 'ID na Loja', 'Preco', 'Preco Promocional', 'Nome Loja (Multilojas)']})


def _patch_module(module: ModuleType) -> None:
    name = getattr(module, '__name__', '')
    if name == 'bling_app_zero.core.bling_direct_sender':
        patch_direct_sender(module)
    elif name == 'bling_app_zero.core.bling_price_sender_guarded':
        patch_price_sender(module)


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, 'create_module', None)
        return create_module(spec) if create_module is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in TARGET_MODULES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PatchLoader):
            return spec
        spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    for module_name in list(TARGET_MODULES):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            _patch_module(loaded)
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_direct_sender', 'patch_price_sender']
