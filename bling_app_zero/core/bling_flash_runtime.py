from __future__ import annotations

import os
from typing import Any

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_flash_runtime.py'
_INSTALLED = False
FULL_MODE_ENV = 'BLING_API_FULL_VERIFY'


def _full_mode_enabled() -> bool:
    return str(os.getenv(FULL_MODE_ENV, '')).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}


def _status_ok(status: Any) -> bool:
    try:
        return int(status) < 400
    except Exception:
        return False


def install_flash_api_mode() -> bool:
    """Instala o modo Flash para envio API.

    O modo normal precisa ser rápido e concluir. Diagnóstico profundo fica atrás
    de BLING_API_FULL_VERIFY=1. Aqui removemos, no fluxo padrão, os reforços
    campo a campo, rotas de imagem e GETs repetidos por produto.
    """
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        if _full_mode_enabled():
            add_audit_event(
                'bling_flash_runtime_skipped_full_mode',
                area='BLING_PERF',
                status='INFO',
                details={'env': FULL_MODE_ENV, 'responsible_file': RESPONSIBLE_FILE},
            )
            _INSTALLED = True
            return False

        from bling_app_zero.core import bling_v3_product_client as module
        BlingV3ProductClient = module.BlingV3ProductClient

        original_update = getattr(BlingV3ProductClient, '_blingflash_original_update_product', None)
        if original_update is None:
            setattr(BlingV3ProductClient, '_blingflash_original_update_product', BlingV3ProductClient.update_product)
        original_create = getattr(BlingV3ProductClient, '_blingflash_original_create_product', None)
        if original_create is None:
            setattr(BlingV3ProductClient, '_blingflash_original_create_product', BlingV3ProductClient.create_product)

        def update_product_flash(self, product_id: str, payload: dict[str, Any]):
            attempts: list[dict[str, Any]] = []
            final_payload = module._force_defaults(payload)
            persisted: dict[str, Any] = {}
            for method in ('PUT', 'PATCH'):
                status, data, text = self.request(method, f'/produtos/{product_id}', final_payload)
                attempts.append({
                    'method': method,
                    'path': f'/produtos/{product_id}',
                    'label': 'flash.product.full',
                    'status': status,
                    'payload_keys': sorted(final_payload.keys()),
                    'changed_fields': module._fields(final_payload),
                    'response_preview': text,
                    'mode': 'flash_api_one_payload',
                })
                if int(status) == 404:
                    break
                if _status_ok(status):
                    persisted = self.get_product(str(product_id))
                    break
            ok = any(_status_ok(item.get('status')) for item in attempts)
            add_audit_event(
                'bling_flash_product_update_finished',
                area='BLING_PERF',
                status='OK' if ok else 'AVISO',
                details={
                    'product_id': str(product_id),
                    'ok': ok,
                    'attempts': attempts,
                    'mode': 'flash_api_one_payload_one_get_no_image_scan',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return module.BlingV3Result(ok=ok, product_id=str(product_id), status='updated' if ok else 'failed', attempts=tuple(attempts), persisted=persisted)

        def create_product_flash(self, payload: dict[str, Any]):
            final_payload = module._force_defaults(payload)
            status, data, text = self.request('POST', '/produtos', final_payload)
            product_id = module._product_id(data)
            attempt = {
                'method': 'POST',
                'path': '/produtos',
                'label': 'flash.product.create',
                'status': status,
                'payload_keys': sorted(final_payload.keys()),
                'changed_fields': module._fields(final_payload),
                'response_preview': text,
                'mode': 'flash_api_create_one_payload',
            }
            if _status_ok(status) and product_id:
                try:
                    self.get_product(str(product_id))
                except Exception:
                    pass
                add_audit_event(
                    'bling_flash_product_created',
                    area='BLING_PERF',
                    status='OK',
                    details={'product_id': str(product_id), 'attempt': attempt, 'responsible_file': RESPONSIBLE_FILE},
                )
                return str(product_id), [attempt]
            add_audit_event(
                'bling_flash_product_create_failed',
                area='BLING_PERF',
                status='AVISO',
                details={'status': status, 'attempt': attempt, 'responsible_file': RESPONSIBLE_FILE},
            )
            return '', [attempt]

        BlingV3ProductClient.update_product = update_product_flash
        BlingV3ProductClient.create_product = create_product_flash
        _INSTALLED = True
        add_audit_event(
            'bling_flash_runtime_installed',
            area='BLING_PERF',
            status='OK',
            details={
                'mode': 'flash_default',
                'full_mode_env': FULL_MODE_ENV,
                'rules': ['one full payload', 'one GET after success', 'no field-by-field patches', 'no image endpoint scan'],
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return True
    except Exception as exc:
        _INSTALLED = True
        add_audit_event(
            'bling_flash_runtime_install_failed',
            area='BLING_PERF',
            status='AVISO',
            details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False


__all__ = ['install_flash_api_mode']
