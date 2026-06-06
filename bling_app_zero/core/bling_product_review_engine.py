from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_product_review_engine.py'

NAME_ALIASES = ('nome', 'produto', 'titulo', 'título', 'descricao produto', 'descrição produto', 'title')
DESCRIPTION_ALIASES = ('descricao', 'descrição', 'descricao curta', 'descrição curta', 'descricao_complementar', 'descrição_complementar', 'detalhes')
CODE_ALIASES = ('codigo', 'código', 'sku', 'ref', 'referencia', 'referência', 'cod produto', 'cod')
GTIN_ALIASES = ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean')
PRICE_ALIASES = ('preco', 'preço', 'preco unitario', 'preço unitário', 'valor', 'valor venda')
IMAGE_ALIASES = ('imagens', 'imagem', 'url imagens', 'url imagem', 'fotos', 'foto', 'image', 'images')
BRAND_ALIASES = ('marca', 'fabricante', 'brand')
CATEGORY_ALIASES = ('categoria', 'categoria produto', 'categoria do produto', 'breadcrumb')
UNIT_ALIASES = ('unidade', 'un')
NCM_ALIASES = ('ncm',)
URL_ALIASES = ('url', 'link', 'url produto', 'url_produto', 'link produto', 'origem url')

BLOCKED_BRAND_TERMS = ('mega center', 'megacenter', 'mega-center', 'stoqui', 'loja')
DEFAULT_UNIT = 'UN'
DEFAULT_TYPE = 'P'
DEFAULT_STATUS = 'A'
DEFAULT_CATEGORY = 'Geral'
DEFAULT_PRICE = '0.01'


@dataclass(frozen=True)
class ProductReviewSummary:
    total: int
    ready: int
    completed: int
    warning: int
    critical: int


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in (('ã', 'a'), ('á', 'a'), ('à', 'a'), ('â', 'a'), ('é', 'e'), ('ê', 'e'), ('í', 'i'), ('ó', 'o'), ('ô', 'o'), ('õ', 'o'), ('ú', 'u'), ('ç', 'c')):
        text = text.replace(old, new)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _clean(value: object) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    if text.lower() in {'nan', 'none', 'null'}:
        return ''
    return re.sub(r'\s+', ' ', text).strip()


def _find_col(columns: list[str], aliases: tuple[str, ...]) -> str:
    alias_keys = [_norm(alias) for alias in aliases]
    for column in columns:
        key = _norm(column)
        if any(alias == key or alias in key for alias in alias_keys):
            return column
    return ''


def _ensure_col(df: pd.DataFrame, preferred: str, aliases: tuple[str, ...]) -> str:
    existing = _find_col([str(c) for c in df.columns], aliases)
    if existing:
        return existing
    df[preferred] = ''
    return preferred


def _digits(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _valid_gtin(value: object) -> str:
    digits = _digits(value)
    return digits if len(digits) in {8, 12, 13, 14} else ''


def _float_text(value: object) -> str:
    text = str(value or '').replace('R$', '').replace(' ', '').strip()
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    text = re.sub(r'[^0-9.\-]+', '', text)
    try:
        number = float(text)
        return f'{number:.2f}'
    except Exception:
        return ''


def _first(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        if column and column in row.index:
            value = _clean(row.get(column, ''))
            if value:
                return value
    return ''


def _generated_code(row: pd.Series, url_col: str, name: str, gtin: str) -> str:
    source = '|'.join([name, gtin, _clean(row.get(url_col, '')) if url_col else ''])
    digest = hashlib.sha1(source.encode('utf-8', errors='ignore')).hexdigest()[:10].upper()
    return f'AUTO-{digest}'


def _safe_brand(value: str) -> str:
    brand = _clean(value)
    if not brand:
        return ''
    low = brand.lower()
    if any(term in low for term in BLOCKED_BRAND_TERMS):
        return ''
    return brand[:80]


def review_dataframe_before_bling(df: pd.DataFrame, *, operation: str = '') -> tuple[pd.DataFrame, ProductReviewSummary]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df, ProductReviewSummary(0, 0, 0, 0, 0)

    out = df.copy().fillna('')
    columns = [str(c) for c in out.columns]

    name_col = _ensure_col(out, 'nome', NAME_ALIASES)
    desc_col = _ensure_col(out, 'descricao', DESCRIPTION_ALIASES)
    code_col = _ensure_col(out, 'codigo', CODE_ALIASES)
    gtin_col = _ensure_col(out, 'gtin', GTIN_ALIASES)
    price_col = _ensure_col(out, 'preco', PRICE_ALIASES)
    image_col = _ensure_col(out, 'imagens', IMAGE_ALIASES)
    brand_col = _ensure_col(out, 'marca', BRAND_ALIASES)
    category_col = _ensure_col(out, 'categoria', CATEGORY_ALIASES)
    unit_col = _ensure_col(out, 'unidade', UNIT_ALIASES)
    ncm_col = _ensure_col(out, 'ncm', NCM_ALIASES)
    url_col = _find_col([str(c) for c in out.columns], URL_ALIASES)

    review_status: list[str] = []
    completed_fields: list[str] = []
    warning_fields: list[str] = []
    critical_fields: list[str] = []
    ready = completed = warning = critical = 0

    for index, row in out.iterrows():
        completed_now: list[str] = []
        warnings_now: list[str] = []
        critical_now: list[str] = []

        name = _clean(row.get(name_col, ''))
        desc = _clean(row.get(desc_col, ''))
        gtin = _valid_gtin(row.get(gtin_col, ''))
        code = _clean(row.get(code_col, ''))
        price = _float_text(row.get(price_col, ''))
        images = _clean(row.get(image_col, ''))
        brand = _safe_brand(row.get(brand_col, ''))
        category = _clean(row.get(category_col, ''))
        unit = _clean(row.get(unit_col, ''))
        ncm = _digits(row.get(ncm_col, ''))[:8]

        if not name:
            name = desc or code or gtin
            if name:
                out.at[index, name_col] = name[:160]
                completed_now.append('nome')

        if not desc and name:
            out.at[index, desc_col] = name
            completed_now.append('descricao')

        if gtin and _clean(row.get(gtin_col, '')) != gtin:
            out.at[index, gtin_col] = gtin
            completed_now.append('gtin_limpo')
        elif not gtin and _clean(row.get(gtin_col, '')):
            out.at[index, gtin_col] = ''
            warnings_now.append('gtin_invalido_removido')

        if not code:
            code = gtin or _generated_code(row, url_col, name, gtin)
            out.at[index, code_col] = code
            completed_now.append('codigo')

        if not price:
            out.at[index, price_col] = DEFAULT_PRICE
            completed_now.append('preco_padrao')

        if not unit:
            out.at[index, unit_col] = DEFAULT_UNIT
            completed_now.append('unidade_padrao')

        if not category:
            out.at[index, category_col] = DEFAULT_CATEGORY
            completed_now.append('categoria_padrao')

        if brand != _clean(row.get(brand_col, '')):
            out.at[index, brand_col] = brand
            warnings_now.append('marca_loja_removida')

        if ncm and len(ncm) == 8:
            out.at[index, ncm_col] = ncm
        elif _clean(row.get(ncm_col, '')):
            out.at[index, ncm_col] = ''
            warnings_now.append('ncm_invalido_removido')

        if not images:
            warnings_now.append('imagens_ausentes')

        final_name = _clean(out.at[index, name_col])
        final_code = _clean(out.at[index, code_col])
        final_desc = _clean(out.at[index, desc_col])
        if not final_name:
            critical_now.append('nome')
        if not final_code:
            critical_now.append('codigo')
        if not final_desc:
            warnings_now.append('descricao_ausente')

        if critical_now:
            status = 'CRITICO'
            critical += 1
        elif warnings_now and completed_now:
            status = 'COMPLETADO_COM_AVISO'
            completed += 1
            warning += 1
        elif warnings_now:
            status = 'AVISO'
            warning += 1
        elif completed_now:
            status = 'COMPLETADO'
            completed += 1
        else:
            status = 'PRONTO'
            ready += 1

        review_status.append(status)
        completed_fields.append(', '.join(completed_now))
        warning_fields.append(', '.join(dict.fromkeys(warnings_now)))
        critical_fields.append(', '.join(dict.fromkeys(critical_now)))

    out['bling_review_status'] = review_status
    out['bling_review_completed_fields'] = completed_fields
    out['bling_review_warning_fields'] = warning_fields
    out['bling_review_critical_fields'] = critical_fields

    summary = ProductReviewSummary(total=len(out), ready=ready, completed=completed, warning=warning, critical=critical)
    add_audit_event(
        'bling_product_review_engine_finished',
        area='BLING_ENVIO',
        status='OK' if critical == 0 else 'AVISO',
        details={
            'operation': operation,
            'total': summary.total,
            'ready': summary.ready,
            'completed': summary.completed,
            'warning': summary.warning,
            'critical': summary.critical,
            'mode': 'review_complete_before_api_do_not_block_noncritical',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return out.fillna(''), summary


__all__ = ['ProductReviewSummary', 'review_dataframe_before_bling']
