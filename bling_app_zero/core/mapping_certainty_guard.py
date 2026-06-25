from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind

RESPONSIBLE_FILE = 'bling_app_zero/core/mapping_certainty_guard.py'

GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
NCM_FORMAT_RE = re.compile(r'^\d{4}[\.\s-]?\d{2}[\.\s-]?\d{2}$')
NUMBER_RE = re.compile(r'^-?\d+(?:[\.,]\d+)?$')
INTEGER_RE = re.compile(r'^-?\d+$')
PRICE_RE = re.compile(r'(?:R\$\s*)?-?\d{1,9}(?:[\.,]\d{2})')
URL_RE = re.compile(r'https?://|www\.', re.I)
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)|cdn|image|imagem|foto', re.I)
TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
BREADCRUMB_RE = re.compile(r'\s(?:>|/|\\|\|)\s')

DESCRIPTION_KINDS = {'descricao', 'descricao_curta', 'descricao_complementar', 'nome_apoio'}
CODE_KINDS = {'codigo', 'id_produto'}
PRICE_KINDS = {'preco_unitario', 'preco_custo'}


@dataclass(frozen=True)
class MappingCertainty:
    ok: bool
    reason: str
    target_kind: str = ''
    source_kind: str = ''
    sample_count: int = 0


def normalize_header(value: object) -> str:
    text = str(value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def compact_header(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', '', normalize_header(value))


def values_for_column(df: Any, column: str, limit: int = 120) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    try:
        series = df[column].dropna().astype(str)
    except Exception:
        return []
    for value in series.head(limit * 3):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null', '<na>'}:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def _digits(value: str) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _all(values: list[str], predicate) -> bool:
    return bool(values) and all(predicate(value) for value in values)


def _any_header_term(value: object, terms: tuple[str, ...]) -> bool:
    key = normalize_header(value)
    return any(term in key for term in terms)


def _equivalent_headers(a: object, b: object) -> bool:
    left = compact_header(a)
    right = compact_header(b)
    return bool(left and right and left == right)


def _kind_compatible(target_kind: str, source_kind: str) -> bool:
    if target_kind == source_kind and target_kind != 'custom':
        return True
    groups = [DESCRIPTION_KINDS, CODE_KINDS, PRICE_KINDS]
    return any(target_kind in group and source_kind in group for group in groups)


def _target_kind(target: str) -> str:
    kind = infer_kind(target)
    if kind != 'custom':
        return kind
    key = normalize_header(target)
    if any(term in key for term in ('ncm', 'classificacao fiscal', 'classificação fiscal')):
        return 'ncm'
    if any(term in key for term in ('descricao', 'descrição', 'nome', 'titulo', 'título', 'produto')):
        return 'descricao'
    if any(term in key for term in ('marca', 'fabricante', 'brand')):
        return 'marca'
    if any(term in key for term in ('categoria', 'departamento', 'grupo', 'familia', 'família')):
        return 'categoria'
    if any(term in key for term in ('estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'balanço')):
        return 'estoque'
    if any(term in key for term in ('preco', 'preço', 'valor', 'custo', 'unitario', 'unitário')):
        return 'preco_unitario'
    if any(term in key for term in ('gtin', 'ean', 'codigo barras', 'código barras', 'barra')):
        return 'gtin'
    if any(term in key for term in ('imagem', 'foto', 'url imagem')):
        return 'imagem'
    if any(term in key for term in ('url', 'link')):
        return 'url'
    if any(term in key for term in ('codigo', 'código', 'sku', 'referencia', 'referência', 'ref')):
        return 'codigo'
    return 'custom'


def _source_kind(source: str) -> str:
    return infer_kind(source)


def _header_confirms(target_kind: str, target: str, source: str, source_kind: str) -> bool:
    exact_header = _equivalent_headers(target, source)
    if target_kind == 'custom':
        return exact_header
    if exact_header or _kind_compatible(target_kind, source_kind):
        return True
    terms_by_kind = {
        'ncm': ('ncm', 'classificacao fiscal', 'classificação fiscal'),
        'gtin': ('gtin', 'ean', 'codigo barras', 'código barras', 'barra'),
        'preco_unitario': ('preco', 'preço', 'valor', 'venda', 'unitario', 'unitário'),
        'preco_custo': ('preco', 'preço', 'valor', 'custo', 'compra'),
        'estoque': ('estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'balanço'),
        'imagem': ('imagem', 'foto', 'url imagem'),
        'url': ('url', 'link', 'pagina', 'página'),
        'descricao': ('descricao', 'descrição', 'nome', 'titulo', 'título', 'produto'),
        'descricao_curta': ('descricao', 'descrição', 'resumo', 'curta'),
        'descricao_complementar': ('descricao', 'descrição', 'complementar', 'completa', 'ficha', 'caracteristica', 'característica'),
        'marca': ('marca', 'fabricante', 'brand'),
        'categoria': ('categoria', 'departamento', 'grupo', 'familia', 'família'),
        'codigo': ('codigo', 'código', 'sku', 'referencia', 'referência', 'ref'),
        'id_produto': ('id', 'codigo', 'código', 'sku'),
    }
    return _any_header_term(source, terms_by_kind.get(target_kind, ()))


def _is_gtin(value: str) -> bool:
    return bool(GTIN_RE.fullmatch(_digits(value)))


def _is_ncm(value: str, header_confirms: bool) -> bool:
    digits = _digits(value)
    if len(digits) != 8:
        return False
    text = str(value or '').strip()
    return header_confirms or (text != digits and bool(NCM_FORMAT_RE.fullmatch(text)))


def _is_url(value: str) -> bool:
    return bool(URL_RE.search(str(value or '')))


def _is_image(value: str) -> bool:
    text = str(value or '')
    if '|' in text:
        parts = [part.strip() for part in text.split('|') if part.strip()]
        return bool(parts) and all(_is_image(part) for part in parts)
    return bool(_is_url(text) and IMAGE_RE.search(text))


def _is_price(value: str) -> bool:
    text = str(value or '').strip().lower()
    if not text:
        return False
    return bool(('r$' in text or 'preco' in text or 'preço' in text or 'valor' in text or PRICE_RE.search(text)) and re.search(r'\d+[\.,]\d{2}', text))


def _is_integer(value: str) -> bool:
    text = str(value or '').strip()
    if not INTEGER_RE.fullmatch(text.replace(' ', '')):
        return False
    digits = _digits(text)
    return bool(digits) and len(digits) <= 7


def _is_text(value: str) -> bool:
    return bool(TEXT_RE.search(str(value or '')))


def _is_safe_description(values: list[str]) -> bool:
    return _all(values, lambda value: _is_text(value) and not _is_url(value) and not _is_price(value) and not _is_gtin(value))


def _is_safe_short_text(values: list[str], max_avg_len: int = 45) -> bool:
    if not _all(values, lambda value: _is_text(value) and not _is_url(value) and not _is_price(value) and not _is_gtin(value)):
        return False
    avg_len = sum(len(value) for value in values) / max(len(values), 1)
    return avg_len <= max_avg_len


def is_certain_mapping(df_source: Any, target: str, source: str) -> MappingCertainty:
    target = str(target or '').strip()
    source = str(source or '').strip()
    if not target or not source:
        return MappingCertainty(False, 'campo vazio')
    if not isinstance(df_source, pd.DataFrame) or source not in df_source.columns:
        return MappingCertainty(False, 'coluna de origem inexistente')

    values = values_for_column(df_source, source)
    if not values:
        return MappingCertainty(False, 'sem amostras reais preenchidas')

    target_kind = _target_kind(target)
    source_kind = _source_kind(source)
    header_ok = _header_confirms(target_kind, target, source, source_kind)
    if not header_ok:
        return MappingCertainty(False, 'cabeçalho não confirma o campo de destino', target_kind, source_kind, len(values))

    if target_kind == 'ncm':
        ok = _all(values, lambda value: _is_ncm(value, header_ok))
        return MappingCertainty(ok, 'NCM confirmado por cabeçalho e conteúdo' if ok else 'NCM sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'gtin':
        ok = _all(values, _is_gtin)
        return MappingCertainty(ok, 'GTIN confirmado por cabeçalho e conteúdo' if ok else 'GTIN não confirmado nas amostras', target_kind, source_kind, len(values))

    if target_kind in PRICE_KINDS:
        ok = _all(values, _is_price)
        return MappingCertainty(ok, 'preço confirmado por cabeçalho e conteúdo' if ok else 'preço sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'estoque':
        ok = _all(values, _is_integer) and not _any_header_term(source, ('preco', 'preço', 'valor', 'custo'))
        return MappingCertainty(ok, 'estoque confirmado por cabeçalho e conteúdo' if ok else 'estoque sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'imagem':
        ok = _all(values, _is_image)
        return MappingCertainty(ok, 'imagem confirmada por cabeçalho e conteúdo' if ok else 'imagem sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'url':
        ok = _all(values, _is_url)
        return MappingCertainty(ok, 'URL confirmada por cabeçalho e conteúdo' if ok else 'URL sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind in DESCRIPTION_KINDS:
        ok = _is_safe_description(values)
        return MappingCertainty(ok, 'texto descritivo confirmado por cabeçalho e conteúdo' if ok else 'descrição sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'marca':
        ok = _is_safe_short_text(values, 45)
        return MappingCertainty(ok, 'marca confirmada por cabeçalho e conteúdo' if ok else 'marca sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'categoria':
        ok = _is_safe_description(values)
        return MappingCertainty(ok, 'categoria confirmada por cabeçalho e conteúdo' if ok else 'categoria sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind in CODE_KINDS:
        ok = not _all(values, _is_gtin) and not _all(values, _is_price) and not _all(values, _is_url)
        return MappingCertainty(ok, 'código confirmado por cabeçalho e conteúdo' if ok else 'código sem validação de conteúdo', target_kind, source_kind, len(values))

    if target_kind == 'custom':
        ok = _equivalent_headers(target, source)
        return MappingCertainty(ok, 'campo customizado confirmado por nome idêntico' if ok else 'campo customizado sem certeza máxima', target_kind, source_kind, len(values))

    ok = _kind_compatible(target_kind, source_kind)
    return MappingCertainty(ok, 'mapeamento confirmado por cabeçalho e conteúdo' if ok else 'sem certeza máxima', target_kind, source_kind, len(values))


def is_unique_certain_mapping(df_source: Any, target: str, source: str) -> MappingCertainty:
    result = is_certain_mapping(df_source, target, source)
    if not result.ok:
        return result
    if not isinstance(df_source, pd.DataFrame):
        return result
    matches = [column for column in df_source.columns if is_certain_mapping(df_source, target, str(column)).ok]
    if len(matches) == 1 and str(matches[0]) == str(source):
        return result
    return MappingCertainty(False, f'ambíguo: {len(matches)} colunas possíveis', result.target_kind, result.source_kind, result.sample_count)


def filter_mapping_to_certain(df_source: Any, mapping: dict[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    used: set[str] = set()
    for target, source in dict(mapping or {}).items():
        target_text = str(target)
        source_text = str(source or '').strip()
        if not source_text or source_text in used:
            filtered[target_text] = ''
            continue
        certainty = is_unique_certain_mapping(df_source, target_text, source_text)
        if certainty.ok:
            filtered[target_text] = source_text
            used.add(source_text)
        else:
            filtered[target_text] = ''
    return filtered


__all__ = [
    'MappingCertainty',
    'filter_mapping_to_certain',
    'is_certain_mapping',
    'is_unique_certain_mapping',
    'normalize_header',
    'values_for_column',
]
