"""Safety guard for Bling product image limits.

Bling rejects product creation when more than 6 images are sent. This module is
loaded automatically by Python in normal app startup and patches only the Bling
product preparation/sending paths.

The preferred flow is the visible rule in the same rules/resources group as
GTIN and image separator. The runtime guard remains as a last safety net and
respects the central user rule ``limit_bling_images``.
"""
from __future__ import annotations

import importlib
import importlib.abc
import re
import sys
from collections.abc import Iterable
from typing import Any

MAX_BLING_IMAGES = 6
_TARGET_MODULES = {
    'bling_app_zero.core.bling_pre_send_defaults',
    'bling_app_zero.core.bling_direct_sender_smart',
    'bling_app_zero.core.verified_api_sender',
    'bling_app_zero.core.blingfix_verified_runtime_patch',
}
_IMAGE_KEY_HINTS = ('imagem', 'imagens', 'image', 'images', 'foto', 'fotos', 'midia')
_URL_SPLIT_RE = re.compile(r'[|;,\n\r]+')
_RULES_SESSION_KEY = 'bling_user_rules'
_CENTRAL_LIMIT_KEY = 'limit_bling_images'
_DECISION_SESSION_KEY = 'ai_real_bling_image_limit_decision'
_GUARD_SESSION_KEY = 'bling_image_limit_guard_enabled'
_SKIP_DECISIONS = {'nao_aplicar', 'não_aplicar', 'skip', 'skipped', 'disabled', 'false'}


def _image_limit_guard_enabled() -> bool:
    try:
        st = importlib.import_module('streamlit')
        state = getattr(st, 'session_state', None)
        if state is None:
            return True

        rules = state.get(_RULES_SESSION_KEY)
        if isinstance(rules, dict) and _CENTRAL_LIMIT_KEY in rules:
            return bool(rules.get(_CENTRAL_LIMIT_KEY, True))

        decision = str(state.get(_DECISION_SESSION_KEY) or '').strip().lower()
        if decision in _SKIP_DECISIONS:
            return False
        if _GUARD_SESSION_KEY in state:
            return bool(state.get(_GUARD_SESSION_KEY))
    except Exception:
        return True
    return True


def _is_image_key(key: Any) -> bool:
    text = str(key or '').strip().lower()
    return any(hint in text for hint in _IMAGE_KEY_HINTS)


def _looks_like_url(value: Any) -> bool:
    text = str(value or '').strip().lower()
    return text.startswith('http://') or text.startswith('https://')


def _dedupe_items(items: Iterable[Any]) -> list[Any]:
    kept: list[Any] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            marker = str(item.get('link') or item.get('url') or item.get('src') or item).strip()
        else:
            marker = str(item).strip()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        kept.append(item)
        if len(kept) >= MAX_BLING_IMAGES:
            break
    return kept


def _limit_image_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    pieces = [part.strip() for part in _URL_SPLIT_RE.split(value) if part.strip()]
    image_urls = [part for part in pieces if _looks_like_url(part)]
    if len(pieces) <= MAX_BLING_IMAGES and len(image_urls) <= MAX_BLING_IMAGES:
        return value
    limited = _dedupe_items(image_urls or pieces)
    return '|'.join(str(part).strip() for part in limited)


def _limit_payload_images(payload: Any) -> Any:
    if not _image_limit_guard_enabled():
        return payload
    if isinstance(payload, list):
        return [_limit_payload_images(item) for item in payload[:MAX_BLING_IMAGES]]
    if not isinstance(payload, dict):
        return payload

    updated = dict(payload)
    for key, value in list(updated.items()):
        key_is_image = _is_image_key(key)
        if key == 'midia' and isinstance(value, dict):
            media = dict(value)
            imagens = media.get('imagens')
            if isinstance(imagens, list):
                media['imagens'] = _dedupe_items(imagens)
            updated[key] = media
        elif isinstance(value, list) and key_is_image:
            updated[key] = _dedupe_items(value)
        elif isinstance(value, str) and key_is_image:
            updated[key] = _limit_image_text(value)
        elif isinstance(value, dict):
            updated[key] = _limit_payload_images(value)
    return updated


def _limit_payload_variant(value: Any) -> Any:
    """Protege variantes do sender inteligente.

    O sender smart retorna tuplas no formato (estratégia, payload, meta). O
    guard antigo tentava limitar a tupla inteira e não entrava no payload. Esta
    função preserva a estrutura e limita apenas o dicionário do payload.
    """
    if isinstance(value, tuple) and len(value) >= 2 and isinstance(value[1], dict):
        limited_payload = _limit_payload_images(value[1])
        return (value[0], limited_payload, *value[2:])
    if isinstance(value, list):
        return [_limit_payload_variant(item) for item in value]
    return _limit_payload_images(value)


def _patch_pre_send_defaults(module: Any) -> None:
    original = getattr(module, 'apply_product_send_defaults', None)
    if not callable(original) or getattr(original, '_bling_image_limit_guard', False):
        return

    def guarded_apply_product_send_defaults(*args: Any, **kwargs: Any) -> Any:
        return _limit_payload_images(original(*args, **kwargs))

    guarded_apply_product_send_defaults._bling_image_limit_guard = True  # type: ignore[attr-defined]
    module.apply_product_send_defaults = guarded_apply_product_send_defaults


def _patch_payload_variants(module: Any) -> None:
    original = getattr(module, '_payload_variants', None)
    if not callable(original) or getattr(original, '_bling_image_limit_guard', False):
        return

    def guarded_payload_variants(*args: Any, **kwargs: Any) -> Any:
        variants = original(*args, **kwargs)
        if isinstance(variants, list):
            return [_limit_payload_variant(item) for item in variants]
        return [_limit_payload_variant(item) for item in variants]

    guarded_payload_variants._bling_image_limit_guard = True  # type: ignore[attr-defined]
    module._payload_variants = guarded_payload_variants


def _patch_force_defaults(module: Any) -> None:
    original = getattr(module, '_force_default_fields', None)
    if not callable(original) or getattr(original, '_bling_image_limit_guard', False):
        return

    def guarded_force_default_fields(*args: Any, **kwargs: Any) -> Any:
        return _limit_payload_images(original(*args, **kwargs))

    guarded_force_default_fields._bling_image_limit_guard = True  # type: ignore[attr-defined]
    module._force_default_fields = guarded_force_default_fields


def _patch_runtime_patch(module: Any) -> None:
    original = getattr(module, 'apply_blingfix_to_verified_module', None)
    if not callable(original) or getattr(original, '_bling_image_limit_guard', False):
        return

    def guarded_apply_blingfix_to_verified_module(target_module: Any) -> Any:
        result = original(target_module)
        _patch_force_defaults(target_module)
        return result

    guarded_apply_blingfix_to_verified_module._bling_image_limit_guard = True  # type: ignore[attr-defined]
    module.apply_blingfix_to_verified_module = guarded_apply_blingfix_to_verified_module


def _patch_module(module: Any) -> None:
    name = getattr(module, '__name__', '')
    if name.endswith('bling_pre_send_defaults'):
        _patch_pre_send_defaults(module)
    if name.endswith('bling_direct_sender_smart'):
        _patch_payload_variants(module)
    if name.endswith('verified_api_sender'):
        _patch_force_defaults(module)
    if name.endswith('blingfix_verified_runtime_patch'):
        _patch_runtime_patch(module)


class _BlingImageLimitLoader(importlib.abc.Loader):
    def __init__(self, loader: importlib.abc.Loader) -> None:
        self._loader = loader

    def create_module(self, spec: Any) -> Any:
        create_module = getattr(self._loader, 'create_module', None)
        if callable(create_module):
            return create_module(spec)
        return None

    def exec_module(self, module: Any) -> None:
        self._loader.exec_module(module)  # type: ignore[attr-defined]
        _patch_module(module)


class _BlingImageLimitFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname not in _TARGET_MODULES:
            return None
        for finder in sys.meta_path:
            if finder is self:
                continue
            find_spec = getattr(finder, 'find_spec', None)
            if not callable(find_spec):
                continue
            spec = find_spec(fullname, path, target)
            if spec and spec.loader and not isinstance(spec.loader, _BlingImageLimitLoader):
                spec.loader = _BlingImageLimitLoader(spec.loader)
                return spec
        return None


if not any(isinstance(finder, _BlingImageLimitFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _BlingImageLimitFinder())

for module_name, module in list(sys.modules.items()):
    if module_name in _TARGET_MODULES:
        _patch_module(module)
