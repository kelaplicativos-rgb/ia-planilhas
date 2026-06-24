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


def _compare_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _compare_value(v) for k, v in sorted(value.items()) if v not in ('', None, {}, [])}
    if isinstance(value, list):
        return [_compare_value(v) for v in value if v not in ('', None, {}, [])]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    text = str(value or '').strip()
    if not text:
        return ''
    numeric = text.replace('.', '').replace(',', '.')
    try:
        if numeric and all(ch in '-0123456789.' for ch in numeric) and any(ch.isdigit() for ch in numeric):
            return round(float(numeric), 6)
    except Exception:
        pass
    return ' '.join(text.split()).casefold()


def _same(current: Any, desired: Any) -> bool:
    return _compare_value(current) == _compare_value(desired)


def _delta_payload(current: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    current = current if isinstance(current, dict) else {}
    out: dict[str, Any] = {}
    for key, value in dict(desired or {}).items():
        if value in ('', None, {}, []):
            continue
        current_value = current.get(key)
        if not _same(current_value, value):
            out[key] = value
    return out


def _strip_media(payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload if isinstance(payload, dict) else {})
    for key in ('midia', 'imagens', 'images'):
        out.pop(key, None)
    return out


def _install_incremental_product_update_guard() -> None:
    """Produto existente: GET atual, compara e envia PATCH só dos campos diferentes.

    BLINGFIX: mídia é tratada em etapa separada, com GET depois de cada tentativa.
    Antes o sistema disparava várias estruturas de imagem em sequência; uma
    estrutura aceita podia persistir e uma tentativa posterior podia limpar a mídia.
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

    def _has_saved_images(saved: dict[str, Any]) -> bool:
        try:
            return bool(client_mod._persistence_report(saved).get('imagens'))
        except Exception:
            return False

    def _apply_media_with_verification(self, product_id: str, desired_payload: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
        media_options = _dedupe_options(client_mod._media_payloads(desired_payload))
        last_saved: dict[str, Any] = {}
        for label, item in media_options:
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
                'delta_only': True,
                'media_verified_step': True,
                'no_put_full_replace': True,
            })
            if status in {401, 403, 404}:
                break
            if int(status) < 400:
                last_saved = self.get_product(product_id)
                if _has_saved_images(last_saved):
                    add_audit_event(
                        'verified_api_sender_media_persisted_and_stopped',
                        area='BLING_ENVIO',
                        status='OK',
                        details={'product_id': str(product_id), 'label': label, 'attempts': attempts[-4:], 'rule': 'parar na primeira estrutura de imagem persistida', 'responsible_file': RESPONSIBLE_FILE},
                    )
                    return last_saved
        if last_saved:
            add_audit_event(
                'verified_api_sender_media_not_persisted_after_all_shapes',
                area='BLING_ENVIO',
                status='AVISO',
                details={'product_id': str(product_id), 'attempts': attempts[-8:], 'rule': 'imagem pendente não bloqueia lote; produto segue com demais campos', 'responsible_file': RESPONSIBLE_FILE},
            )
        return last_saved

    def update_product_incremental(self, product_id: str, payload: dict[str, Any]):
        attempts: list[dict[str, Any]] = []
        desired_payload = client_mod._clean(payload if isinstance(payload, dict) else {})
        saved_before = self.get_product(product_id)
        delta = _delta_payload(saved_before, desired_payload)
        expected_media = bool(client_mod._image_links(desired_payload))
        base_delta = client_mod._clean(_strip_media(delta))

        if not base_delta and not expected_media:
            add_audit_event(
                'verified_api_sender_no_product_delta_detected',
                area='BLING_ENVIO',
                status='OK',
                details={'product_id': str(product_id), 'desired_fields': sorted(desired_payload.keys()), 'rule': 'sem diferenças reais; nenhum PATCH enviado', 'responsible_file': RESPONSIBLE_FILE},
            )
            return client_mod.BlingV3Result(ok=True, product_id=str(product_id), status='unchanged_no_delta', attempts=tuple(), persisted=saved_before)

        options: list[tuple[str, dict[str, Any]]] = []
        if base_delta:
            options.append(('product.delta.patch', base_delta))
            options.extend(client_mod._description_payloads(base_delta))
            options.extend(client_mod._detail_payloads(base_delta))
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
                'delta_only': True,
                'no_put_full_replace': True,
            })
            if status in {401, 403, 404}:
                break

        persisted = self._after_write(product_id, base_delta or desired_payload, attempts) if attempts else saved_before
        if expected_media:
            media_saved = _apply_media_with_verification(self, product_id, desired_payload, attempts)
            if media_saved:
                persisted = media_saved

        ok = bool(attempts) and any(isinstance(item.get('status'), int) and int(item.get('status')) < 400 for item in attempts)
        if expected_media and not attempts:
            ok = True
        add_audit_event(
            'verified_api_sender_incremental_product_update_guard_used',
            area='BLING_ENVIO',
            status='OK' if ok else 'AVISO',
            details={'product_id': str(product_id), 'requested_fields': sorted(desired_payload.keys()), 'delta_fields': sorted(delta.keys()), 'base_delta_fields': sorted(base_delta.keys()), 'expected_media': expected_media, 'attempts': attempts[-12:], 'rule': 'PATCH somente dos campos diferentes; mídia separada e verificada; vazios não apagam dados', 'responsible_file': RESPONSIBLE_FILE},
        )
        return client_mod.BlingV3Result(ok=ok, product_id=str(product_id), status='updated_delta_only', attempts=tuple(attempts), persisted=persisted)

    update_product_incremental._mapeiaai_incremental_patch_only = True
    client_mod.BlingV3ProductClient.update_product = update_product_incremental
    add_audit_event(
        'verified_api_sender_incremental_product_update_guard_installed',
        area='BLING_ENVIO',
        status='OK',
        details={'rule': 'produto existente usa PATCH incremental somente com delta real, mídia separada e verificada, nunca PUT full replace', 'responsible_file': RESPONSIBLE_FILE},
    )


def send_verified_products(df, *, limit=None, progress_callback=None):
    from bling_app_zero.core import verified_api_sender

    _apply_payload_guard(verified_api_sender)
    _install_incremental_product_update_guard()
    fixed_df = apply_dataframe_send_defaults(df)
    result = _original_send_verified_products(fixed_df, limit=limit, progress_callback=progress_callback)
    return _with_enriched_errors(result, fixed_df)


__all__ = ['RESPONSIBLE_FILE', 'send_verified_products']
