from __future__ import annotations

from typing import Any

from bling_app_zero.core import bling_direct_sender_smart as _base

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_smart_image_limit_clean.py'
MAX_BLING_IMAGES = 6

_ORIGINAL_PAYLOAD_VARIANTS = _base._payload_variants
_ORIGINAL_PREVIEW_PAYLOADS = _base.preview_payloads

# Reexports usados pelo sender inteligente com comparação.
BASE_RESPONSIBLE_FILE = getattr(_base, 'RESPONSIBLE_FILE', 'bling_app_zero/core/bling_direct_sender_smart.py')
SEND_TIMEOUT = getattr(_base, 'SEND_TIMEOUT', 30)
_cadastro_schema_error = _base._cadastro_schema_error
_emit_progress = _base._emit_progress
_headers = _base._headers
_resolve_product_id = _base._resolve_product_id
_secret = _base._secret
_url = _base._url
is_direct_send_available = _base.is_direct_send_available


def _limit_midia_images(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_limit_midia_images(item) for item in payload[:MAX_BLING_IMAGES]]
    if not isinstance(payload, dict):
        return payload

    out = dict(payload)
    midia = out.get('midia')
    if isinstance(midia, dict):
        media = dict(midia)
        imagens = media.get('imagens')
        if isinstance(imagens, list):
            media['imagens'] = imagens[:MAX_BLING_IMAGES]
        out['midia'] = media

    for key, value in list(out.items()):
        if key == 'midia':
            continue
        if isinstance(value, dict):
            out[key] = _limit_midia_images(value)
    return out


def _limit_variant_images(variant: Any) -> Any:
    if isinstance(variant, tuple) and len(variant) >= 2 and isinstance(variant[1], dict):
        return (variant[0], _limit_midia_images(variant[1]), *variant[2:])
    return variant


def _payload_variants(token: dict[str, Any], row: Any, mapping: dict[str, str]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    variants = _ORIGINAL_PAYLOAD_VARIANTS(token, row, mapping)
    cleaned = [_limit_variant_images(item) for item in variants]
    return [item for item in cleaned if isinstance(item, tuple)]


def preview_payloads(df: Any, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    preview = _ORIGINAL_PREVIEW_PAYLOADS(df, operation, limit=limit)
    output: list[dict[str, Any]] = []
    for item in preview:
        if not isinstance(item, dict):
            output.append(item)
            continue
        current = dict(item)
        payload = current.get('payload')
        if isinstance(payload, dict):
            current['payload'] = _limit_midia_images(payload)
        output.append(current)
    return output


def apply_blingclean_patch() -> None:
    if getattr(_base, '_blingclean_image_limit_patch_installed', False):
        return
    _base._payload_variants = _payload_variants
    _base.preview_payloads = preview_payloads
    _base.MAX_BLING_IMAGES = MAX_BLING_IMAGES
    _base._blingclean_image_limit_patch_installed = True


__all__ = [
    'BASE_RESPONSIBLE_FILE',
    'MAX_BLING_IMAGES',
    'RESPONSIBLE_FILE',
    'SEND_TIMEOUT',
    '_cadastro_schema_error',
    '_emit_progress',
    '_headers',
    '_payload_variants',
    '_resolve_product_id',
    '_secret',
    '_url',
    'apply_blingclean_patch',
    'is_direct_send_available',
    'preview_payloads',
]
