from __future__ import annotations

from copy import deepcopy
from typing import Any

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.verified_api_sender import send_verified_products as _original_send_verified_products
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults
from bling_app_zero.core.blingfix_verified_runtime_patch import apply_blingfix_to_verified_module as _apply_payload_guard
from bling_app_zero.core.verified_error_context import enrich_verified_errors

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_api_sender_guarded.py'


def _with_enriched_errors(result: DirectSendResult, df) -> DirectSendResult:
    enriched = enrich_verified_errors(tuple(result.errors or ()), df)
    if enriched == tuple(result.errors or ()):  # nada para enriquecer
        return result
    return DirectSendResult(
        attempted=result.attempted,
        sent=result.sent,
        failed=result.failed,
        skipped=result.skipped,
        errors=enriched,
        not_found_indices=tuple(result.not_found_indices or ()),
    )


def _install_incremental_product_update_guard() -> None:
    """Evita atualização destrutiva de produto existente.

    Quando o produto já existe no Bling, a planilha tratada deve funcionar como
    origem dos campos a atualizar. Campos vazios/não mapeados não podem apagar
    dados existentes. Por isso substituímos o update full PUT por PATCHs
    incrementais somente com valores presentes no payload final.
    """
    from bling_app_zero.core import bling_v3_product_client as client_mod

    current = getattr(client_mod.BlingV3ProductClient, 'update_product', None)
    if getattr(current, '_mapeiaai_incremental_patch_only', False):
        return

    def _dedupe_options(options: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        for label, payload in options:
            clean_payload = client_mod._clean(payload)
            if not clean_payload:
                continue
            marker = f'{label}:{repr(sorted(clean_payload.items()))}'
            if marker in seen:
                continue
            seen.add(marker)
            out.append((label, clean_payload))
        return out

    def update_product_incremental(self, product_id: str, payload: dict[str, Any]):
        attempts: list[dict[str, Any]] = []
        partial_payload = client_mod._clean(payload if isinstance(payload, dict) else {})
        if not partial_payload:
            saved = self.get_product(product_id)
            return client_mod.BlingV3Result(ok=True, product_id=str(product_id), status='unchanged', attempts=tuple(), persisted=saved)

        options: list[tuple[str, dict[str, Any]]] = [('product.incremental.patch', partial_payload)]
        no_media = deepcopy(partial_payload)
        no_media.pop('midia', None)
        no_media.pop('imagens', None)
        if no_media != partial_payload:
            options.append(('product.incremental.no_media.patch', no_media))
        options.extend(client_mod._description_payloads(partial_payload))
        options.extend(client_mod._detail_payloads(partial_payload))
        options.extend(client_mod._media_payloads(partial_payload))
        options = _dedupe_options(options)

        for label, item in options:
            status, _data, text = self.request('PATCH', f'/produtos/{product_id}', item)
            attempts.append({
                'method': 'PATCH',
                'path': f'/produtos/{product_id}',
                'label': label,
                'status': status,
                'payload_keys': sorted(item.keys()),
                'changed_fields': client_mod._fields(item),
                'response_preview': text,
                'incremental_update_only': True,
                'no_put_full_replace': True,
            })
            if status in {401, 403, 404}:
                break

        persisted = self._after_write(product_id, partial_payload, attempts)
        ok = any(isinstance(item.get('status'), int) and int(item.get('status')) < 400 for item in attempts)
        add_audit_event(
            'verified_api_sender_incremental_product_update_guard_used',
            area='BLING_ENVIO',
            status='OK' if ok else 'AVISO',
            details={
                'product_id': str(product_id),
                'attempts': attempts[-12:],
                'rule': 'PATCH incremental; campos vazios não removem dados existentes',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return client_mod.BlingV3Result(ok=ok, product_id=str(product_id), status='updated_incremental', attempts=tuple(attempts), persisted=persisted)

    update_product_incremental._mapeiaai_incremental_patch_only = True
    client_mod.BlingV3ProductClient.update_product = update_product_incremental
    add_audit_event(
        'verified_api_sender_incremental_product_update_guard_installed',
        area='BLING_ENVIO',
        status='OK',
        details={'rule': 'produto existente usa PATCH incremental, nunca PUT full replace', 'responsible_file': RESPONSIBLE_FILE},
    )


def send_verified_products(df, *, limit=None, progress_callback=None):
    from bling_app_zero.core import verified_api_sender

    _apply_payload_guard(verified_api_sender)
    _install_incremental_product_update_guard()
    fixed_df = apply_dataframe_send_defaults(df)
    result = _original_send_verified_products(fixed_df, limit=limit, progress_callback=progress_callback)
    return _with_enriched_errors(result, fixed_df)


__all__ = ['RESPONSIBLE_FILE', 'send_verified_products']
