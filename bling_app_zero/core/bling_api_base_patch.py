from __future__ import annotations

import sys
from typing import Any

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_api_base_patch.py'
CORRECT_API_BASE_URL = 'https://api.bling.com.br/Api/v3'
LEGACY_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
PATCHED_MODULES = (
    'bling_app_zero.core.bling_direct_sender',
    'bling_app_zero.core.bling_direct_sender_safe',
    'bling_app_zero.core.bling_direct_sender_smart',
    'bling_app_zero.core.bling_autocadastro_api',
    'bling_app_zero.ui.home_bling_api_flow',
)
_PATCH_DONE = False
_FORCE_UPDATE_PATCH_DONE = False


def _patch_module(module: Any, module_name: str) -> bool:
    changed = False
    try:
        current = str(getattr(module, 'DEFAULT_API_BASE_URL', '') or '').rstrip('/')
        if current == LEGACY_API_BASE_URL:
            setattr(module, 'DEFAULT_API_BASE_URL', CORRECT_API_BASE_URL)
            changed = True
    except Exception:
        pass
    return changed


def _patch_complete_product_update() -> bool:
    global _FORCE_UPDATE_PATCH_DONE
    if _FORCE_UPDATE_PATCH_DONE:
        return False
    changed = False
    try:
        from bling_app_zero.core import bling_smart_product_diff
        from bling_app_zero.core.bling_v3_product_client import BlingV3ProductClient

        def update_existing_product_if_changed_v3(*, token, product_id, variants, url_builder, headers_builder, timeout, responsible_file):
            client = BlingV3ProductClient(token=token, url_builder=url_builder, headers_builder=headers_builder, timeout=timeout)
            attempts = []
            for strategy, payload, meta in variants:
                result = client.update_product(str(product_id), payload)
                for attempt in result.attempts:
                    item = dict(attempt)
                    item['strategy'] = strategy
                    item['confidence'] = meta.get('confidence') if isinstance(meta, dict) else None
                    item['mode'] = 'bling_v3_product_client_rebuild'
                    attempts.append(item)
                if result.ok:
                    return 'updated', attempts
            return 'failed', attempts

        original = getattr(bling_smart_product_diff, '_blingfix_original_update_existing_product_if_changed', None)
        if original is None:
            setattr(
                bling_smart_product_diff,
                '_blingfix_original_update_existing_product_if_changed',
                bling_smart_product_diff.update_existing_product_if_changed,
            )
        bling_smart_product_diff.update_existing_product_if_changed = update_existing_product_if_changed_v3
        smart_diff = sys.modules.get('bling_app_zero.core.bling_direct_sender_smart_diff')
        if smart_diff is not None:
            setattr(smart_diff, 'update_existing_product_if_changed', update_existing_product_if_changed_v3)
        changed = True
    except Exception as exc:
        add_audit_event(
            'bling_complete_product_update_patch_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )

    _FORCE_UPDATE_PATCH_DONE = True
    return changed


def _install_review() -> bool:
    try:
        from bling_app_zero.core.bling_review_runtime import install_review_before_api
        return bool(install_review_before_api())
    except Exception as exc:
        add_audit_event(
            'bling_review_install_call_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False


def patch_bling_api_base_urls() -> None:
    global _PATCH_DONE
    changed_modules: list[str] = []
    for module_name in PATCHED_MODULES:
        module = sys.modules.get(module_name)
        if module is not None and _patch_module(module, module_name):
            changed_modules.append(module_name)
    complete_update_patched = _patch_complete_product_update()
    review_engine_patched = _install_review()
    if changed_modules or complete_update_patched or review_engine_patched or not _PATCH_DONE:
        add_audit_event(
            'bling_api_base_runtime_patch_applied',
            area='BLING_ENVIO',
            status='OK' if changed_modules or complete_update_patched or review_engine_patched else 'SEM_ALTERACAO',
            details={
                'changed_modules': changed_modules,
                'correct_api_base_url': CORRECT_API_BASE_URL,
                'complete_product_update_patched': complete_update_patched,
                'review_engine_patched': review_engine_patched,
                'smart_diff_alias_patch': True,
                'api_rebuild_client': 'bling_app_zero/core/bling_v3_product_client.py',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    _PATCH_DONE = True


__all__ = ['CORRECT_API_BASE_URL', 'patch_bling_api_base_urls']
