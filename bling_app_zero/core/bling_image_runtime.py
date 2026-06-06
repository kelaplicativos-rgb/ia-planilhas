from __future__ import annotations

import os

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_image_runtime.py'
_INSTALLED = False
DEEP_SCAN_ENV = 'BLING_IMAGE_DEEP_SCAN'


def _deep_scan_enabled() -> bool:
    return str(os.getenv(DEEP_SCAN_ENV, '')).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}


def _has_images(saved: dict) -> bool:
    if not isinstance(saved, dict):
        return False
    midia = saved.get('midia') if isinstance(saved.get('midia'), dict) else {}
    imagens = saved.get('imagens') or midia.get('imagens')
    if isinstance(imagens, list):
        return any(bool(item) for item in imagens)
    if isinstance(imagens, dict):
        return any(_has_images({'imagens': value}) for value in imagens.values())
    return bool(imagens)


def install_product_image_client() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        if not _deep_scan_enabled():
            try:
                from bling_app_zero.core.bling_flash_runtime import install_flash_api_mode
                install_flash_api_mode()
            except Exception as exc:
                add_audit_event('bling_image_runtime_flash_install_failed', area='BLING_PERF', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
            _INSTALLED = True
            add_audit_event('bling_image_runtime_skipped_fast_mode', area='BLING_IMAGEM', status='OK', details={'deep_scan_env': DEEP_SCAN_ENV, 'responsible_file': RESPONSIBLE_FILE})
            return True

        from bling_app_zero.core.bling_product_image_client import push_product_images
        from bling_app_zero.core.bling_v3_product_client import BlingV3ProductClient

        original = getattr(BlingV3ProductClient, '_blingimage_original_after_write', None)
        if original is None:
            original = BlingV3ProductClient._after_write
            setattr(BlingV3ProductClient, '_blingimage_original_after_write', original)

        def after_write_with_image_client(self, product_id: str, payload: dict, attempts: list):
            saved = original(self, product_id, payload, attempts)
            if _has_images(saved):
                return saved
            ok, image_attempts = push_product_images(product_id=str(product_id), payload=payload, url_builder=self.url_builder, headers=self.headers, get_product=self.get_product)
            if image_attempts:
                attempts.extend(image_attempts)
            refreshed = self.get_product(str(product_id))
            add_audit_event('bling_image_runtime_after_write_finished', area='BLING_IMAGEM', status='OK' if ok or _has_images(refreshed) else 'AVISO', details={'product_id': str(product_id), 'image_client_ok': ok, 'has_images_after': _has_images(refreshed), 'attempts': image_attempts[-20:], 'responsible_file': RESPONSIBLE_FILE})
            return refreshed

        BlingV3ProductClient._after_write = after_write_with_image_client
        _INSTALLED = True
        add_audit_event('bling_image_runtime_installed', area='BLING_IMAGEM', status='OK', details={'responsible_file': RESPONSIBLE_FILE, 'client_file': 'bling_app_zero/core/bling_product_image_client.py'})
        return True
    except Exception as exc:
        _INSTALLED = True
        add_audit_event('bling_image_runtime_install_failed', area='BLING_IMAGEM', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False


__all__ = ['install_product_image_client']
