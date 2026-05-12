from __future__ import annotations

import hashlib
import json
from typing import Any

from bling_app_zero.core.user_rules import get_user_rules

SIGNATURE_RULE_KEYS = (
    'clean_invalid_gtin',
    'normalize_image_separator',
    'invalid_gtin_mode',
    'image_separator',
    'auto_product_code',
    'unique_product_code',
    'custom_rules',
)


def _safe_rules_payload(rules: dict[str, Any]) -> dict[str, Any]:
    return {key: rules.get(key) for key in SIGNATURE_RULE_KEYS}


def rules_signature() -> str:
    """Assinatura das regras que afetam o CSV final.

    Impede download final cacheado quando a sidebar muda recursos como
    Limpar GTIN inválido, Separar imagens por |, Código automático ou regras manuais.
    """
    payload = _safe_rules_payload(get_user_rules())
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:16]


__all__ = ['rules_signature']
