from __future__ import annotations

import re
from typing import Any, Callable

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/brand_runtime_patch.py'
EXTRA_KNOWN_BRANDS = (
    'Imenso',
)
BRAND_STOPWORDS = {
    '', 'caixa', 'som', 'bluetooth', 'produto', 'produtos', 'fone', 'headset', 'carregador',
    'cabo', 'cabos', 'controle', 'mouse', 'teclado', 'radio', 'rádio', 'relogio', 'relógio',
    'smartwatch', 'suporte', 'adaptador', 'universal', 'portatil', 'portátil', 'led', 'usb',
    'hdmi', 'tipo', 'gamer', 'sem', 'com', 'para', 'de', 'da', 'do', 'das', 'dos',
}


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def _title_tokens(title: object) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9&'.-]{1,30}", str(title or ''))


def _looks_like_brand_token(token: str) -> bool:
    clean = token.strip(" -|/.,;:'\"")
    if len(clean) < 3 or len(clean) > 30:
        return False
    normalized = _norm(clean)
    if normalized in BRAND_STOPWORDS:
        return False
    if normalized.isdigit():
        return False
    if re.search(r'\d', clean):
        return False
    return clean[0].isupper()


def _fallback_brand_from_title(title: object) -> str:
    # Último recurso seguro: pula palavras genéricas de categoria e pega a primeira
    # palavra com cara de marca. Isso resolve casos como "Caixa de Som Imenso" sem
    # transformar "Caixa", "Som" ou "Bluetooth" em marca.
    for token in _title_tokens(title):
        if _looks_like_brand_token(token):
            return token.strip(" -|/.,;:'\"")
    return ''


def install_brand_runtime_patch() -> bool:
    try:
        from bling_app_zero.core import bling_direct_sender_smart as smart
    except Exception as exc:
        add_audit_event('brand_runtime_patch_import_failed', area='MARCA', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    if getattr(smart, '_blingfix_brand_runtime_patch_installed', False):
        return False

    existing = tuple(getattr(smart, 'KNOWN_BRANDS', ()) or ())
    smart.KNOWN_BRANDS = tuple(dict.fromkeys((*existing, *EXTRA_KNOWN_BRANDS)))

    original_resolve: Callable[..., Any] | None = getattr(smart, '_blingfix_original_resolve_brand', None)
    if original_resolve is None:
        original_resolve = smart._resolve_brand
        setattr(smart, '_blingfix_original_resolve_brand', original_resolve)

    def resolve_brand_with_title_fallback(title: object, fallback_brand: object = '') -> str:
        resolved = str(original_resolve(title, fallback_brand) or '').strip()
        if resolved:
            return resolved
        return _fallback_brand_from_title(title)

    smart._resolve_brand = resolve_brand_with_title_fallback
    smart._blingfix_brand_runtime_patch_installed = True
    add_audit_event(
        'brand_runtime_patch_installed',
        area='MARCA',
        status='OK',
        details={
            'extra_known_brands': list(EXTRA_KNOWN_BRANDS),
            'fallback_title_detection': True,
            'reason': 'Captar marca real no título sem usar loja/modelo/palavras genéricas como marca.',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_brand_runtime_patch']
