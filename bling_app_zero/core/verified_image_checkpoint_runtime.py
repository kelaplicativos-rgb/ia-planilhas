from __future__ import annotations

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.product_persistence_check import product_persistence_flags

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_image_checkpoint_runtime.py'


def _payload_has_images(payload: dict) -> bool:
    midia = payload.get('midia') if isinstance(payload.get('midia'), dict) else {}
    imagens = midia.get('imagens') or payload.get('imagens') or payload.get('images')
    if isinstance(imagens, dict):
        return any(bool(v) for v in imagens.values())
    if isinstance(imagens, list):
        return bool(imagens)
    return bool(imagens)


def install_verified_image_checkpoint_runtime() -> bool:
    try:
        from bling_app_zero.core.bling_v3_product_client import BlingV3ProductClient

        current_update = BlingV3ProductClient.update_product
        current_create = BlingV3ProductClient.create_product
        if getattr(current_update, '_verified_image_checkpoint_wrapper', False) and getattr(current_create, '_verified_image_checkpoint_wrapper', False):
            add_audit_event('verified_image_checkpoint_runtime_already_active', area='BLING_IMAGEM', status='OK', details={'dynamic_push_lookup': True, 'responsible_file': RESPONSIBLE_FILE})
            return False

        original_update = current_update
        original_create = current_create

        def _check_image(self, product_id: str, payload: dict, attempts: list, persisted: dict) -> dict:
            flags = product_persistence_flags(persisted or {})
            if flags.get('imagens') or not product_id or not _payload_has_images(payload):
                add_audit_event(
                    'verified_image_checkpoint_skipped',
                    area='BLING_IMAGEM',
                    status='OK',
                    details={
                        'product_id': str(product_id),
                        'already_has_image': flags.get('imagens'),
                        'payload_has_images': _payload_has_images(payload),
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                return persisted or {}

            from bling_app_zero.core import bling_product_image_client

            ok, image_attempts = bling_product_image_client.push_product_images(
                product_id=str(product_id),
                payload=payload,
                url_builder=self.url_builder,
                headers=self.headers,
                get_product=self.get_product,
            )
            if image_attempts:
                attempts.extend(dict(item) for item in image_attempts[-10:])
            refreshed = self.get_product(str(product_id))
            after = product_persistence_flags(refreshed or {})
            add_audit_event(
                'verified_image_checkpoint_finished',
                area='BLING_IMAGEM',
                status='OK' if after.get('imagens') else 'PENDENTE',
                details={
                    'product_id': str(product_id),
                    'image_client_ok': ok,
                    'image_persisted': after.get('imagens'),
                    'dynamic_push_lookup': True,
                    'attempts': image_attempts[-8:],
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return refreshed or persisted or {}

        def update_product_with_image_checkpoint(self, product_id: str, payload: dict):
            result = original_update(self, product_id, payload)
            attempts = [dict(item) for item in result.attempts]
            persisted = _check_image(self, str(product_id), payload, attempts, dict(result.persisted or {}))
            return result.__class__(ok=result.ok, product_id=result.product_id, status=result.status, attempts=tuple(attempts), persisted=persisted)

        def create_product_with_image_checkpoint(self, payload: dict):
            product_id, attempts = original_create(self, payload)
            attempts_list = [dict(item) for item in attempts]
            if product_id:
                saved = self.get_product(str(product_id))
                _check_image(self, str(product_id), payload, attempts_list, saved or {})
            return product_id, attempts_list

        update_product_with_image_checkpoint._verified_image_checkpoint_wrapper = True
        create_product_with_image_checkpoint._verified_image_checkpoint_wrapper = True
        BlingV3ProductClient.update_product = update_product_with_image_checkpoint
        BlingV3ProductClient.create_product = create_product_with_image_checkpoint
        add_audit_event('verified_image_checkpoint_runtime_installed', area='BLING_IMAGEM', status='OK', details={'reentrant': True, 'dynamic_push_lookup': True, 'responsible_file': RESPONSIBLE_FILE})
        return True
    except Exception as exc:
        add_audit_event('verified_image_checkpoint_runtime_install_failed', area='BLING_IMAGEM', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False


__all__ = ['install_verified_image_checkpoint_runtime']
