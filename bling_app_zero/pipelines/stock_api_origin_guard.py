from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/stock_api_origin_guard.py'
URL_COLUMNS = ('url', 'link', 'produto_url', 'url_produto', 'origem url', 'link produto')
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


def _is_universal_op(op: str) -> bool:
    return str(op or '').strip().lower() in UNIVERSAL_OPS


def _keep_api_rows_without_url(out: pd.DataFrame, *, op: str) -> pd.DataFrame | None:
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
                'reason': 'Origem por site sem coluna URL, mas com identificador e quantidade/saldo. Mantendo linhas para fluxo unificado/API/download.',
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
                'reason': 'Origem por site sem coluna URL, mas com campos de produto válidos. Mantendo linhas para fluxo unificado/API/download.',
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
    url_col = _find_col(out, URL_COLUMNS)
    op = str(operation or '').strip().lower()

    if not url_col:
        kept = _keep_api_rows_without_url(out, op=op)
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

    if not url_col:
        add_audit_event(
            'site_pipeline_live_origin_blocked_without_url',
            area='SITE',
            status='BLOQUEADO',
            details={'rows_before': len(out), 'operation': op, 'responsible_file': RESPONSIBLE_FILE},
        )
        return out.iloc[0:0].copy()

    before = len(out)
    out = out[out[url_col].map(lambda value: _same_public_domain(clean_cell(value), allowed_domains))].copy()
    removed = before - len(out)
    if removed:
        add_audit_event(
            'site_pipeline_live_origin_rows_removed',
            area='SITE',
            status='AVISO',
            details={'rows_before': before, 'rows_after': len(out), 'removed': removed, 'url_column': url_col, 'responsible_file': RESPONSIBLE_FILE},
        )
    return out.fillna('')


__all__ = ['filter_origin_rows_for_operation']