from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/stock_api_origin_guard.py'
URL_COLUMNS = ('url', 'link', 'produto_url', 'url_produto', 'origem url', 'link produto', 'link externo')
IMAGE_URL_COLUMN_HINTS = ('imagem', 'imagens', 'foto', 'fotos', 'media', 'midia', 'mídia', 'cdn', 'thumb', 'thumbnail')
DIMENSION_COLUMN_HINTS = ('largura', 'altura', 'profundidade', 'comprimento', 'peso', 'volume', 'volumes', 'dimensao', 'dimensão')
STOCK_ID_COLUMNS = ('codigo', 'código', 'sku', 'gtin', 'ean', 'id produto', 'id_produto', 'id bling', 'id_bling')
STOCK_QTY_COLUMNS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'balanço', 'stock', 'movimentacao de estoque', 'movimentação de estoque')
CADASTRO_CORE_COLUMNS = ('nome', 'descricao', 'descrição', 'codigo', 'código', 'sku', 'preco', 'preço', 'imagens', 'imagem', 'gtin', 'marca', 'categoria')
UNIVERSAL_OPS = {'', 'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


def _key(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _find_col(df: pd.DataFrame, aliases: tuple[str, ...]) -> str:
    alias_keys = [_key(alias) for alias in aliases]
    for column in df.columns:
        col_key = _key(column)
        if any(alias == col_key or alias in col_key for alias in alias_keys):
            return str(column)
    return ''


def _is_image_url_column(column: object) -> bool:
    key = _key(column)
    if not key:
        return False
    return any(hint in key for hint in IMAGE_URL_COLUMN_HINTS)


def _is_dimension_column(column: object) -> bool:
    key = _key(column)
    if not key:
        return False
    return any(hint in key for hint in DIMENSION_COLUMN_HINTS)


def _is_product_url_column(column: object) -> bool:
    key = _key(column)
    if not key or _is_image_url_column(column) or _is_dimension_column(column):
        return False
    if key in {'url', 'link'}:
        return True
    has_url_or_link = bool(re.search(r'\b(url|link|pagina|page)\b', key))
    has_product_context = bool(re.search(r'\b(produto|product|externo|externa|origem)\b', key))
    return bool(has_url_or_link and has_product_context)


def _find_product_url_col(df: pd.DataFrame) -> str:
    for column in df.columns:
        if _is_product_url_column(column):
            return str(column)
    return ''


def _count_cols(df: pd.DataFrame, aliases: tuple[str, ...]) -> int:
    alias_keys = [_key(alias) for alias in aliases]
    count = 0
    for column in df.columns:
        col_key = _key(column)
        if any(alias == col_key or alias in col_key for alias in alias_keys):
            count += 1
    return count


def _domain(value: str) -> str:
    try:
        return urlparse(str(value or '')).netloc.lower().replace('www.', '')
    except Exception:
        return ''


def _input_public_domains(raw_urls: str) -> set[str]:
    domains: set[str] = set()
    for item in re.split(r'[\n,;]+', str(raw_urls or '')):
        item = item.strip()
        if not item.startswith(('http://', 'https://')):
            continue
        host = _domain(item)
        if host:
            domains.add(host)
    return domains


def _same_public_domain(url: str, allowed_domains: set[str]) -> bool:
    host = _domain(url)
    if not host:
        return False
    return any(host == domain or host.endswith('.' + domain) for domain in allowed_domains)


def _has_stock_payload_columns(df: pd.DataFrame) -> bool:
    return bool(isinstance(df, pd.DataFrame) and not df.empty and _find_col(df, STOCK_ID_COLUMNS) and _find_col(df, STOCK_QTY_COLUMNS))


def _has_cadastro_payload_columns(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    useful_cols = _count_cols(df, CADASTRO_CORE_COLUMNS)
    has_name = bool(_find_col(df, ('nome', 'descricao', 'descrição')))
    has_price_or_code = bool(_find_col(df, ('preco', 'preço', 'codigo', 'código', 'sku', 'gtin')))
    return bool(useful_cols >= 2 and has_name and has_price_or_code)


def _has_any_payload_columns(df: pd.DataFrame) -> bool:
    return _has_stock_payload_columns(df) or _has_cadastro_payload_columns(df)


def _is_universal_op(op: str) -> bool:
    return str(op or '').strip().lower() in UNIVERSAL_OPS


def _keep_api_rows_without_url(out: pd.DataFrame, *, op: str, reason_suffix: str = '') -> pd.DataFrame | None:
    normalized = str(op or '').strip().lower()
    universal = _is_universal_op(normalized)

    if (normalized == 'estoque' or universal) and _has_stock_payload_columns(out):
        add_audit_event(
            'site_pipeline_live_origin_url_filter_skipped_for_stock_or_universal',
            area='SITE',
            status='OK',
            details={
                'rows_before': len(out),
                'operation': normalized or 'universal',
                'reason': 'Origem por site sem URL de produto confiável, mas com identificador e quantidade/saldo. Mantendo linhas para fluxo unificado/API/download.' + str(reason_suffix or ''),
                'columns': list(map(str, out.columns))[:30],
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return out.fillna('')

    if (normalized == 'cadastro' or universal) and _has_cadastro_payload_columns(out):
        add_audit_event(
            'site_pipeline_live_origin_url_filter_skipped_for_cadastro_or_universal',
            area='SITE',
            status='OK',
            details={
                'rows_before': len(out),
                'operation': normalized or 'universal',
                'reason': 'Origem por site sem URL de produto confiável, mas com campos de produto válidos. Mantendo linhas para fluxo unificado/API/download.' + str(reason_suffix or ''),
                'columns': list(map(str, out.columns))[:30],
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return out.fillna('')

    return None


def filter_origin_rows_for_operation(df: pd.DataFrame, raw_urls: str, *, operation: str = '') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna('')
    product_url_col = _find_product_url_col(out)
    legacy_url_col = _find_col(out, URL_COLUMNS)
    ignored_bad_url_col = legacy_url_col if legacy_url_col and not product_url_col and (_is_image_url_column(legacy_url_col) or _is_dimension_column(legacy_url_col)) else ''
    op = str(operation or '').strip().lower()

    if not product_url_col:
        suffix = f' Coluna ignorada como falsa URL de produto: {ignored_bad_url_col}.' if ignored_bad_url_col else ''
        kept = _keep_api_rows_without_url(out, op=op, reason_suffix=suffix)
        if kept is not None:
            return kept

    allowed_domains = _input_public_domains(raw_urls)
    if not allowed_domains:
        kept = _keep_api_rows_without_url(out, op=op)
        if kept is not None:
            return kept
        add_audit_event(
            'site_pipeline_live_origin_blocked_without_input_domain',
            area='SITE',
            status='BLOQUEADO',
            details={'rows_before': len(out), 'operation': op, 'reason': 'Sem domínio público de entrada e sem payload reconhecido.', 'responsible_file': RESPONSIBLE_FILE},
        )
        return out.iloc[0:0].copy()

    if not product_url_col:
        add_audit_event(
            'site_pipeline_live_origin_blocked_without_product_url',
            area='SITE',
            status='BLOQUEADO',
            details={
                'rows_before': len(out),
                'operation': op,
                'ignored_bad_url_column': ignored_bad_url_col,
                'reason': 'Não há URL de produto confiável; URL de imagem/dimensão/CDN não pode ser usada para filtrar domínio.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return out.iloc[0:0].copy()

    before = len(out)
    filtered = out[out[product_url_col].map(lambda value: _same_public_domain(clean_cell(value), allowed_domains))].copy()
    removed = before - len(filtered)
    if removed:
        add_audit_event(
            'site_pipeline_live_origin_rows_removed',
            area='SITE',
            status='AVISO',
            details={'rows_before': before, 'rows_after': len(filtered), 'removed': removed, 'url_column': product_url_col, 'responsible_file': RESPONSIBLE_FILE},
        )

    if filtered.empty and _is_universal_op(op) and _has_any_payload_columns(out):
        add_audit_event(
            'site_pipeline_live_origin_domain_filter_empty_preserved_for_universal',
            area='SITE',
            status='CORRIGIDO',
            details={
                'rows_before': before,
                'url_column': product_url_col,
                'operation': op or 'universal',
                'reason': 'Filtro de domínio removeria todas as linhas, mas a origem universal possui payload válido. Mantendo linhas para revisão/mapeamento.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return out.fillna('')

    return filtered.fillna('')


__all__ = ['filter_origin_rows_for_operation']