from __future__ import annotations

from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults, apply_product_send_defaults

RESPONSIBLE_FILE = 'bling_app_zero/core/payload_guard.py'


def _digits(value) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _valid_gtin(value) -> str:
    digits = _digits(value)
    return digits if len(digits) in {8, 12, 13, 14} else ''


def is_real_product_url(value) -> bool:
    text = str(value or '').strip().lower()
    if not text.startswith(('http://', 'https://')):
        return False
    blocked = ('/storage/', 'product_images', 'product-images', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.avif')
    if any(item in text for item in blocked):
        return False
    return any(item in text for item in ('/produto/', '/produtos/', '/product/', '/products/', '/p/'))


def _product_page_only_link(verified, row) -> str:
    try:
        items = list(row.items())
    except Exception:
        return ''
    preferred_names = {'linkexterno', 'link externo', 'url produto', 'link produto', 'produto_url', 'source_url', 'url_origem', 'link_origem'}
    normalized_names = {verified._norm_col(item) for item in preferred_names}
    for key, value in items:
        if verified._norm_col(key) in normalized_names and is_real_product_url(value):
            return str(value or '').strip()
    for key, value in items:
        normalized = verified._norm_col(key)
        if any(item in normalized for item in ('imagem', 'image', 'foto', 'thumbnail')):
            continue
        if is_real_product_url(value):
            return str(value or '').strip()
    return ''


def _safe_brand_for_payload(verified, payload, row_fixed) -> str:
    payload_fixed = apply_product_send_defaults(payload)
    for candidate in (
        payload_fixed.get('marca') if isinstance(payload_fixed, dict) else '',
        payload_fixed.get('Marca') if isinstance(payload_fixed, dict) else '',
        row_fixed.get('marca') if isinstance(row_fixed, dict) else '',
        row_fixed.get('Marca') if isinstance(row_fixed, dict) else '',
    ):
        text = str(candidate or '').strip()
        if verified._brand_ok(text):
            return text
    return 'Genérico'


def apply_payload_guard_to_verified_module(verified):
    verified.DEFAULT_UNIT = 'UN'
    verified.DEFAULT_PRODUCTION = 'Terceiros'
    verified.DEFAULT_CONDITION = 'Novo'
    verified.DEFAULT_MEASURE_UNIT = 'Centímetros'

    def product_page_only_link(row) -> str:
        return _product_page_only_link(verified, row)

    def fixed_force_default_fields(payload, row=None):
        if not isinstance(payload, dict):
            return payload
        updated = dict(payload)
        row_fixed = apply_product_send_defaults(row) if row is not None else {}

        updated['marca'] = _safe_brand_for_payload(verified, updated, row_fixed)
        updated['condicao'] = 'Novo'
        updated['producao'] = 'Terceiros'
        updated['unidade'] = 'UN'
        updated['unidadeMedida'] = 'Centímetros'
        if not str(updated.get('departamento') or '').strip():
            updated['departamento'] = 'Adulto Unissex'
        updated['descricaoComplementar'] = ''

        gtin = ''
        for candidate in (
            updated.get('gtin'),
            updated.get('ean'),
            updated.get('gtinEan'),
            updated.get('codigoBarras'),
            row_fixed.get('gtin') if isinstance(row_fixed, dict) else '',
            row_fixed.get('ean') if isinstance(row_fixed, dict) else '',
            row_fixed.get('GTIN/EAN') if isinstance(row_fixed, dict) else '',
            row_fixed.get('codigo de barras') if isinstance(row_fixed, dict) else '',
        ):
            gtin = _valid_gtin(candidate)
            if gtin:
                break

        tributacao = dict(updated.get('tributacao') or {}) if isinstance(updated.get('tributacao'), dict) else {}
        updated['gtin'] = gtin
        updated['ean'] = gtin
        updated['gtinTributario'] = gtin
        tributacao['gtin'] = gtin
        tributacao['ean'] = gtin
        updated['tributacao'] = tributacao

        link = str(updated.get('linkExterno') or '').strip()
        if not is_real_product_url(link):
            link = product_page_only_link(row_fixed) or (product_page_only_link(row) if row is not None else '')
        updated['linkExterno'] = link if is_real_product_url(link) else ''
        return updated

    verified._row_link = product_page_only_link
    verified._force_default_fields = fixed_force_default_fields
    return verified


def normalize_dataframe_for_bling(df):
    return apply_dataframe_send_defaults(df)


__all__ = ['RESPONSIBLE_FILE', 'apply_payload_guard_to_verified_module', 'normalize_dataframe_for_bling', 'is_real_product_url']