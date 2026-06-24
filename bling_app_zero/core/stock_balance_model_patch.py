from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/stock_balance_model_patch.py'
TARGET_MODULE = 'bling_app_zero.core.bling_direct_sender_safe'


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


def _operation_code(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'í': 'i', 'ã': 'a', 'á': 'a', 'ç': 'c', 'é': 'e', 'ó': 'o'}.items():
        text = text.replace(old, new)
    if 'saida' in text or text in {'s', 'retirada', 'remocao', 'remove'}:
        return 'S'
    if 'entrada' in text or text in {'e', 'inclusao', 'adicao', 'add'}:
        return 'E'
    return 'B'


def _api_abs_quantity(module: ModuleType, quantity: float, operation: str) -> int | float:
    number = abs(float(quantity)) if operation in {'E', 'S'} else float(quantity)
    return module._api_number(number)


def _stock_payload_variants(module: ModuleType, product_id: str, deposit_id: str, quantity: float, operation: str, purchase: float | None, cost: float | None, note: str) -> list[dict[str, Any]]:
    base = {'produto': {'id': str(product_id)}, 'deposito': {'id': str(deposit_id)}, 'operacao': operation, 'quantidade': _api_abs_quantity(module, quantity, operation)}
    variants: list[dict[str, Any]] = []
    rich = dict(base)
    if purchase is not None:
        rich['preco'] = module._api_number(float(purchase))
        rich['precoCompra'] = module._api_number(float(purchase))
    if cost is not None:
        rich['precoCusto'] = module._api_number(float(cost))
        rich['custo'] = module._api_number(float(cost))
    if note:
        rich['observacao'] = note
        rich['observacoes'] = note
    variants.append(rich)
    variants.append(base)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in variants:
        clean = module._clean_payload(payload)
        marker = repr(sorted(clean.items()))
        if clean and marker not in seen:
            out.append(clean)
            seen.add(marker)
    return out


def patch_stock_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_stock_balance_model_patched', False):
        return
    aliases = getattr(module, 'COLUMN_ALIASES', None)
    if isinstance(aliases, dict):
        aliases['id'] = _extend_aliases(aliases.get('id', tuple()), 'ID Produto', 'id produto')
        aliases['codigo'] = _extend_aliases(aliases.get('codigo', tuple()), 'Código SKU*', 'Codigo SKU*', 'codigo sku', 'sku')
        aliases['gtin'] = _extend_aliases(aliases.get('gtin', tuple()), 'GTIN/EAN**', 'gtin ean')
        aliases['nome'] = _extend_aliases(aliases.get('nome', tuple()), 'Nome do Produto')
        aliases['deposito'] = _extend_aliases(aliases.get('deposito', tuple()), 'Depósito*', 'Deposito*')
        aliases['quantidade'] = _extend_aliases(aliases.get('quantidade', tuple()), 'Movimentação de Estoque*', 'Movimentacao de Estoque*', 'movimentação de estoque', 'movimentacao de estoque')
        aliases['tipo_lancamento'] = _extend_aliases(aliases.get('tipo_lancamento', tuple()), 'Tipo de lançamento*', 'Tipo de lancamento*', 'tipo de lançamento', 'tipo de lancamento', 'operação estoque', 'operacao estoque')
        aliases['preco_compra'] = _extend_aliases(aliases.get('preco_compra', tuple()), 'Preço de Compra*', 'Preco de Compra*', 'preço de compra', 'preco de compra')
        aliases['preco_custo'] = _extend_aliases(aliases.get('preco_custo', tuple()), 'Preço de Custo', 'Preco de Custo', 'preço custo', 'preco custo')
        aliases['observacao'] = _extend_aliases(aliases.get('observacao', tuple()), 'Observação', 'Observacao', 'observações', 'observacoes')

    def _stock_preview_payloads_model(df, *, limit: int = 5):
        token, _meta = module.load_token()
        mapping = module._column_map(df.columns)
        previews: list[dict[str, Any]] = []
        if not isinstance(token, dict) or not token.get('access_token'):
            return [{'payload': {}, 'status': 'IGNORADO', 'motivo': 'Bling não conectado.'}]
        default_deposit_id = module._resolve_deposit_id(token)
        for _index, row in df.fillna('').head(limit).iterrows():
            quantity = module._number_value(module._value(row, mapping, 'quantidade'))
            operation = _operation_code(module._value(row, mapping, 'tipo_lancamento'))
            product_id = ''
            for candidate in module._row_candidates(row, mapping):
                product_id = module._resolve_product_by_candidate(token, candidate)
                if product_id:
                    break
            deposit_id = module._resolve_deposit_id(token, module._value(row, mapping, 'deposito')) or default_deposit_id
            purchase = module._number_value(module._value(row, mapping, 'preco_compra'))
            cost = module._number_value(module._value(row, mapping, 'preco_custo'))
            note = module._clean_text(module._value(row, mapping, 'observacao'), 180)
            if not product_id:
                previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Produto não resolvido no Bling por ID/Código/SKU/GTIN.'})
            elif not deposit_id:
                previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Depósito não resolvido no Bling.'})
            elif quantity is None:
                previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Movimentação de estoque inválida.'})
            else:
                payloads = _stock_payload_variants(module, product_id, deposit_id, quantity, operation, purchase, cost, note)
                previews.append({'payload': payloads[0], 'status': 'OK', 'motivo': f'Tipo de lançamento: {operation}. Entrada=E, Saída=S, Balanço=B.'})
        return previews

    def _send_stock_dataframe_to_bling_model(df, *, limit=None, progress_callback=None):
        if not hasattr(df, 'columns') or df.empty:
            return module._blocked_empty_result(module.OP_ESTOQUE, progress_callback)
        token, _meta = module.load_token()
        if not isinstance(token, dict) or not token.get('access_token'):
            return module.DirectSendResult(0, 0, 0, len(df), ('Bling não conectado. Conecte o app antes de enviar direto.',))
        rows = df.fillna('').head(limit) if limit else df.fillna('')
        mapping = module._column_map(rows.columns)
        total = len(rows)
        sent = failed = skipped = 0
        errors: list[str] = []
        not_found: list[int] = []
        default_deposit_id = module._resolve_deposit_id(token)
        module._emit_progress(progress_callback, {'stage': 'Iniciando envio de estoque pelo modelo saldo_estoque', 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})
        for position, (index, row) in enumerate(rows.iterrows(), start=1):
            line = int(index) + 1 if isinstance(index, int) else position
            quantity = module._number_value(module._value(row, mapping, 'quantidade'))
            if quantity is None:
                skipped += 1
                if len(errors) < 8:
                    errors.append(f'Linha {line}: Movimentação de Estoque ausente ou inválida.')
                continue
            operation = _operation_code(module._value(row, mapping, 'tipo_lancamento'))
            product_id = ''
            for candidate in module._row_candidates(row, mapping):
                product_id = module._resolve_product_by_candidate(token, candidate)
                if product_id:
                    break
            if not product_id:
                failed += 1
                not_found.append(int(index) if isinstance(index, int) else position - 1)
                if len(errors) < 8:
                    errors.append(f'Linha {line}: produto não encontrado no Bling por ID Produto/Código SKU/GTIN.')
                continue
            deposit_id = module._resolve_deposit_id(token, module._value(row, mapping, 'deposito')) or default_deposit_id
            if not deposit_id:
                failed += 1
                if len(errors) < 8:
                    errors.append(f'Linha {line}: depósito não resolvido no Bling.')
                continue
            purchase = module._number_value(module._value(row, mapping, 'preco_compra'))
            cost = module._number_value(module._value(row, mapping, 'preco_custo'))
            note = module._clean_text(module._value(row, mapping, 'observacao'), 180)
            payload_variants = _stock_payload_variants(module, product_id, deposit_id, quantity, operation, purchase, cost, note)
            ok = False
            last_response = None
            attempts: list[dict[str, Any]] = []
            for payload in payload_variants:
                for method, path in module._stock_endpoint_attempts(product_id):
                    try:
                        response = module.requests.request(method, module._url(path), headers=module._headers(token), json=payload, timeout=module.SEND_TIMEOUT)
                        last_response = response
                        attempts.append({'method': method, 'path': path, 'status': int(response.status_code), 'payload_keys': sorted(payload.keys()), 'operacao': payload.get('operacao'), 'response_preview': str(response.text or '')[:180]})
                        if response.status_code < 400:
                            ok = True
                            break
                        if response.status_code in {401, 403}:
                            break
                    except Exception as exc:
                        attempts.append({'method': method, 'path': path, 'status': 'EXCEPTION', 'error': str(exc)[:180], 'operacao': payload.get('operacao')})
                if ok or (last_response is not None and getattr(last_response, 'status_code', 0) in {401, 403}):
                    break
            if ok:
                sent += 1
            else:
                failed += 1
                status = getattr(last_response, 'status_code', 'sem resposta')
                preview = str(getattr(last_response, 'text', '') or '')[:180]
                if len(errors) < 8:
                    errors.append(f'Linha {line}: Bling recusou estoque ({status}). {preview}')
                _audit(module, 'stock_balance_model_payload_failed', status='AVISO', details={'line': line, 'product_id': product_id, 'deposit_id': deposit_id, 'operation': operation, 'quantity': quantity, 'attempts': attempts[-6:]})
            module._emit_progress(progress_callback, {'stage': 'Enviando estoque ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
        module._emit_progress(progress_callback, {'stage': 'Envio de estoque concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
        _audit(module, 'stock_balance_model_send_finished', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'not_found_count': len(not_found), 'rule': 'Tipo de lançamento respeitado: Entrada E, Saída S, Balanço B'})
        return module.DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple(not_found))

    module._stock_preview_payloads = _stock_preview_payloads_model
    module._send_stock_dataframe_to_bling = _send_stock_dataframe_to_bling_model
    module._mapeiaai_stock_balance_model_patched = True
    _audit(module, 'stock_balance_model_patch_installed', details={'model_columns': ['ID Produto', 'Código SKU*', 'GTIN/EAN**', 'Depósito*', 'Movimentação de Estoque*', 'Tipo de lançamento*', 'Preço de Compra*', 'Preço de Custo', 'Observação']})


def _patch_loaded() -> None:
    loaded = sys.modules.get(TARGET_MODULE)
    if loaded is not None:
        patch_stock_sender(loaded)


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, 'create_module', None)
        return create_module(spec) if create_module is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        if getattr(module, '__name__', '') == TARGET_MODULE:
            patch_stock_sender(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != TARGET_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PatchLoader):
            return spec
        spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    _patch_loaded()
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_stock_sender']
