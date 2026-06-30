from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.html_product_extractor import clean_text

RESPONSIBLE_FILE = 'bling_app_zero/core/source_contract_enrichment.py'
GTIN_RE = re.compile(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+,\d{2}', re.I)
INTEGER_RE = re.compile(r'\b\d+(?:[\.,]\d+)?\b')
NCM_RE = re.compile(r'\b\d{4}\.\d{2}\.\d{2}\b|\b\d{8}\b')
CEST_RE = re.compile(r'\b\d{2}\.\d{3}\.\d{2}\b|\b\d{7}\b')
MEASURE_RE = re.compile(r'\b\d+(?:[\.,]\d+)?\s*(?:cm|mm|m|kg|g|ml|l)\b', re.I)
DATE_RE = re.compile(r'\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b')

ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    'id': ('id', 'id produto', 'product id', 'produto id', 'codigo interno'),
    'codigo': ('codigo', 'código', 'codigo sku', 'código sku', 'sku', 'referencia', 'referência', 'ref', 'modelo'),
    'descricao': ('descricao', 'descrição', 'descricao produto', 'descrição produto', 'nome', 'titulo', 'título', 'produto', 'product name', 'name'),
    'unidade': ('unidade', 'un', 'unit', 'unidade medida', 'unidade de medida'),
    'ncm': ('ncm',),
    'origem': ('origem', 'origem fiscal'),
    'preco': ('preco', 'preço', 'valor', 'price', 'preco unitario', 'preço unitário', 'valor venda'),
    'ipi': ('valor ipi fixo', 'ipi', 'ipi fixo'),
    'observacoes': ('observacoes', 'observações', 'observacao', 'observação', 'obs'),
    'situacao': ('situacao', 'situação', 'status'),
    'estoque': ('estoque', 'saldo', 'quantidade', 'qtd', 'stock', 'balanco', 'balanço'),
    'preco custo': ('preco custo', 'preço custo', 'preco de custo', 'preço de custo', 'custo', 'cost'),
    'cod fornecedor': ('cod fornecedor', 'cód no fornecedor', 'codigo fornecedor', 'código fornecedor', 'supplier code'),
    'fornecedor': ('fornecedor', 'supplier'),
    'localizacao': ('localizacao', 'localização', 'prateleira', 'location'),
    'estoque maximo': ('estoque maximo', 'estoque máximo', 'maximo', 'máximo'),
    'estoque minimo': ('estoque minimo', 'estoque mínimo', 'minimo', 'mínimo'),
    'peso liquido': ('peso liquido', 'peso líquido', 'peso net', 'net weight'),
    'peso bruto': ('peso bruto', 'gross weight'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'),
    'gtin embalagem': ('gtin embalagem', 'gtin/ean da embalagem', 'ean embalagem', 'codigo barras embalagem'),
    'largura': ('largura', 'width'),
    'altura': ('altura', 'height'),
    'profundidade': ('profundidade', 'comprimento', 'depth', 'length'),
    'validade': ('validade', 'data validade', 'expiration', 'vencimento'),
    'descricao fornecedor': ('descricao fornecedor', 'descrição fornecedor', 'descricao do produto no fornecedor'),
    'descricao complementar': ('descricao complementar', 'descrição complementar', 'descricao curta', 'descrição curta', 'description'),
    'itens caixa': ('itens caixa', 'itens p caixa', 'itens por caixa', 'caixa'),
    'produto variacao': ('produto variacao', 'produto variação', 'variacao', 'variação'),
    'tipo producao': ('tipo producao', 'tipo produção', 'producao', 'produção'),
    'tipo item': ('tipo item', 'tipo do item'),
    'tags': ('tags', 'grupo de tags', 'grupo de tags/tags'),
    'tributos': ('tributos', 'tributação', 'tributacao'),
    'codigo pai': ('codigo pai', 'código pai', 'sku pai', 'parent sku'),
    'codigo integracao': ('codigo integracao', 'código integração', 'codigo integração', 'integration code'),
    'grupo produtos': ('grupo produtos', 'grupo de produtos', 'grupo'),
    'marca': ('marca', 'brand'),
    'cest': ('cest',),
    'volumes': ('volumes', 'volume'),
    'cross docking': ('cross docking', 'cross-docking'),
    'url imagens': ('url imagens', 'url imagens externas', 'imagem', 'imagens', 'foto', 'fotos', 'image'),
    'link externo': ('link externo', 'url', 'link', 'href'),
    'garantia': ('garantia', 'meses garantia', 'meses garantia fornecedor'),
    'condicao': ('condicao', 'condição', 'condicao produto', 'condição produto'),
    'frete gratis': ('frete gratis', 'frete grátis', 'free shipping'),
    'fci': ('numero fci', 'número fci', 'fci'),
    'video': ('video', 'vídeo', 'youtube'),
    'departamento': ('departamento', 'department'),
    'preco compra': ('preco compra', 'preço compra', 'preco de compra', 'preço de compra', 'purchase price'),
    'icms st base': ('valor base icms st', 'base icms st'),
    'icms st valor': ('valor icms st', 'icms st'),
    'icms proprio': ('icms proprio', 'icms próprio'),
    'categoria': ('categoria', 'categoria do produto', 'category', 'breadcrumb'),
    'informacoes adicionais': ('informacoes adicionais', 'informações adicionais', 'additional info'),
}

TARGET_GROUP_HINTS: tuple[tuple[str, str], ...] = (
    ('gtin/ean da embalagem', 'gtin embalagem'), ('gtin embalagem', 'gtin embalagem'), ('ean embalagem', 'gtin embalagem'),
    ('gtin/ean', 'gtin'), ('gtin', 'gtin'), ('ean', 'gtin'), ('código de barras', 'gtin'), ('codigo de barras', 'gtin'),
    ('preço de custo', 'preco custo'), ('preco de custo', 'preco custo'), ('preço custo', 'preco custo'), ('preco custo', 'preco custo'),
    ('preço de compra', 'preco compra'), ('preco de compra', 'preco compra'), ('preço compra', 'preco compra'), ('preco compra', 'preco compra'),
    ('preço', 'preco'), ('preco', 'preco'), ('valor ipi', 'ipi'),
    ('estoque max', 'estoque maximo'), ('estoque máximo', 'estoque maximo'), ('estoque maximo', 'estoque maximo'),
    ('estoque min', 'estoque minimo'), ('estoque mínimo', 'estoque minimo'), ('estoque minimo', 'estoque minimo'),
    ('estoque', 'estoque'), ('balanço', 'estoque'), ('balanco', 'estoque'),
    ('peso líquido', 'peso liquido'), ('peso liquido', 'peso liquido'), ('peso bruto', 'peso bruto'), ('largura', 'largura'), ('altura', 'altura'), ('profundidade', 'profundidade'),
    ('data validade', 'validade'), ('validade', 'validade'), ('ncm', 'ncm'), ('cest', 'cest'),
    ('descrição do produto no fornecedor', 'descricao fornecedor'), ('descricao do produto no fornecedor', 'descricao fornecedor'),
    ('descrição complementar', 'descricao complementar'), ('descricao complementar', 'descricao complementar'), ('descrição curta', 'descricao complementar'), ('descricao curta', 'descricao complementar'),
    ('cód no fornecedor', 'cod fornecedor'), ('cod no fornecedor', 'cod fornecedor'), ('fornecedor', 'fornecedor'), ('localização', 'localizacao'), ('localizacao', 'localizacao'),
    ('grupo de tags', 'tags'), ('tags', 'tags'), ('código pai', 'codigo pai'), ('codigo pai', 'codigo pai'), ('código integração', 'codigo integracao'), ('codigo integracao', 'codigo integracao'),
    ('grupo de produtos', 'grupo produtos'), ('marca', 'marca'), ('categoria', 'categoria'), ('url imagens', 'url imagens'), ('imagens', 'url imagens'), ('link externo', 'link externo'),
    ('condição', 'condicao'), ('condicao', 'condicao'), ('frete grátis', 'frete gratis'), ('frete gratis', 'frete gratis'), ('vídeo', 'video'), ('video', 'video'),
    ('departamento', 'departamento'), ('unidade de medida', 'unidade'), ('unidade', 'unidade'),
    ('informações adicionais', 'informacoes adicionais'), ('informacoes adicionais', 'informacoes adicionais'),
    ('observações', 'observacoes'), ('observacoes', 'observacoes'), ('situação', 'situacao'), ('situacao', 'situacao'),
    ('origem', 'origem'), ('código', 'codigo'), ('codigo', 'codigo'), ('descrição', 'descricao'), ('descricao', 'descricao'), ('nome', 'descricao'),
)


def normalize_text(value: object) -> str:
    text = clean_text(value).casefold()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def _compact(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', '', normalize_text(value))


def _nonblank(value: object) -> bool:
    return clean_text(value).casefold() not in {'', 'nan', 'none', 'null', '<na>'}


def _target_group(column: str) -> str:
    key = normalize_text(column)
    for hint, group in TARGET_GROUP_HINTS:
        if normalize_text(hint) in key:
            return group
    return key


def _column_match_score(source_column: str, aliases: Iterable[str]) -> int:
    source_norm = normalize_text(source_column)
    source_compact = _compact(source_column)
    best = 0
    for alias in aliases:
        alias_norm = normalize_text(alias)
        alias_compact = _compact(alias)
        if not alias_norm:
            continue
        if source_norm == alias_norm or source_compact == alias_compact:
            best = max(best, 100)
        elif alias_norm in source_norm or alias_compact in source_compact:
            best = max(best, 70)
        elif source_norm in alias_norm or source_compact in alias_compact:
            best = max(best, 45)
    return best


def _best_source_column(df: pd.DataFrame, target_column: str) -> str:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return ''
    target_norm = normalize_text(target_column)
    target_compact = _compact(target_column)
    for column in map(str, df.columns):
        if normalize_text(column) == target_norm or _compact(column) == target_compact:
            return column
    group = _target_group(target_column)
    aliases = ALIAS_GROUPS.get(group, (target_column,))
    ranked: list[tuple[int, str]] = []
    for column in map(str, df.columns):
        score = _column_match_score(column, aliases)
        if score >= 70:
            ranked.append((score, column))
    if not ranked:
        return ''
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def _valid_gtin(value: object) -> str:
    digits = re.sub(r'\D+', '', clean_text(value))
    if len(digits) not in {8, 12, 13, 14}:
        return ''
    if len(set(digits)) == 1:
        return ''
    total = 0
    body = digits[:-1]
    check = int(digits[-1])
    reversed_digits = list(map(int, reversed(body)))
    for index, digit in enumerate(reversed_digits, start=1):
        total += digit * (3 if index % 2 == 1 else 1)
    expected = (10 - (total % 10)) % 10
    return digits if expected == check else ''


def _row_text(row: pd.Series) -> str:
    values = [clean_text(value) for value in row.astype(str).tolist() if _nonblank(value)]
    return ' '.join(values)[:20000]


def _extract_from_text(text: str, target_column: str) -> str:
    group = _target_group(target_column)
    norm = normalize_text(text)
    if group in {'gtin', 'gtin embalagem'}:
        if not any(marker in norm for marker in ('gtin', 'ean', 'codigo de barras', 'barcode')):
            return ''
        for match in GTIN_RE.finditer(text or ''):
            valid = _valid_gtin(match.group(1))
            if valid:
                return valid
        return ''
    if group in {'preco', 'preco custo', 'preco compra', 'ipi'}:
        match = PRICE_RE.search(text or '')
        return clean_text(match.group(0)) if match else ''
    if group in {'estoque', 'estoque maximo', 'estoque minimo', 'itens caixa', 'volumes', 'cross docking', 'garantia', 'origem'}:
        match = INTEGER_RE.search(text or '')
        return clean_text(match.group(0)).replace(',', '.') if match else ''
    if group == 'ncm':
        match = NCM_RE.search(text or '')
        return clean_text(match.group(0)) if match else ''
    if group == 'cest':
        match = CEST_RE.search(text or '')
        return clean_text(match.group(0)) if match else ''
    if group in {'largura', 'altura', 'profundidade', 'peso liquido', 'peso bruto'}:
        match = MEASURE_RE.search(text or '')
        return clean_text(match.group(0)) if match else ''
    if group == 'validade':
        match = DATE_RE.search(text or '')
        return clean_text(match.group(0)) if match else ''
    return ''


def _copy_or_extract_series(df: pd.DataFrame, target_column: str) -> tuple[pd.Series, str]:
    source_column = _best_source_column(df, target_column)
    if source_column:
        return df[source_column].fillna('').astype(str).map(clean_text), source_column
    extracted = df.apply(lambda row: _extract_from_text(_row_text(row), target_column), axis=1)
    found = int(extracted.map(_nonblank).sum())
    return extracted.fillna('').astype(str), 'texto bruto' if found else ''


def enrich_source_with_requested_columns(df: pd.DataFrame, requested_columns: Iterable[str], *, source: str = '') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    columns = [clean_text(column) for column in requested_columns if clean_text(column)]
    if not columns:
        return df.copy().fillna('').astype(str)

    out = df.copy().fillna('').astype(str)
    filled: dict[str, str] = {}
    for target_column in columns:
        series, origin = _copy_or_extract_series(out, target_column)
        if not origin:
            continue
        if target_column not in out.columns:
            out[target_column] = ''
        current = out[target_column].fillna('').astype(str)
        replacement = []
        changed = 0
        for current_value, candidate_value in zip(current.tolist(), series.tolist()):
            current_text = clean_text(current_value)
            candidate_text = clean_text(candidate_value)
            if not current_text and candidate_text:
                replacement.append(candidate_text)
                changed += 1
            else:
                replacement.append(current_text)
        if changed:
            out[target_column] = replacement
            filled[target_column] = origin

    if filled:
        add_audit_event(
            'source_contract_columns_enriched',
            area='ORIGEM',
            status='OK',
            details={
                'requested_columns': len(columns),
                'filled_columns': filled,
                'source': source,
                'does_not_change_final_contract': True,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    else:
        add_audit_event(
            'source_contract_columns_not_found',
            area='ORIGEM',
            status='AVISO',
            details={'requested_columns': len(columns), 'source': source, 'responsible_file': RESPONSIBLE_FILE},
        )
    return out.fillna('').astype(str)


__all__ = ['enrich_source_with_requested_columns', 'normalize_text']
