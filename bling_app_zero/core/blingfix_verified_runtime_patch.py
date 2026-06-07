from __future__ import annotations

from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults

RESPONSIBLE_FILE = 'bling_app_zero/core/blingfix_verified_runtime_patch.py'


def is_real_product_url(value) -> bool:
    text = str(value or '').strip().lower()
    if not text.startswith(('http://', 'https://')):
        return False
    blocked = ('/storage/', 'product_images', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg')
    if any(item in text for item in blocked):
        return False
    return any(item in text for item in ('/produto/', '/produtos/', '/product/', '/products/', '/p/'))


def apply_blingfix_to_verified_module(verified):
    verified.DEFAULT_UNIT = 'UN'
    verified.DEFAULT_PRODUCTION = 'Terceiros'
    verified.DEFAULT_CONDITION = 'Novo'

    def product_page_only_link(row) -> str:
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

    verified._row_link = product_page_only_link
    return verified


def normalize_dataframe_for_bling(df):
    return apply_dataframe_send_defaults(df)


__all__ = ['RESPONSIBLE_FILE', 'apply_blingfix_to_verified_module', 'normalize_dataframe_for_bling', 'is_real_product_url']
