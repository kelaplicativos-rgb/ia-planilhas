from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind

RESPONSIBLE_FILE = 'bling_app_zero/core/smart_column_profiler.py'

TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?-?\d{1,7}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
NCM_RE = re.compile(r'^\d{4}[\.\s-]?\d{2}[\.\s-]?\d{2}$')
NUMBER_RE = re.compile(r'^-?\d+(?:[\.,]\d+)?$')
INTEGER_RE = re.compile(r'^-?\d+$')
URL_RE = re.compile(r'https?://', re.I)
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)', re.I)
BREADCRUMB_RE = re.compile(r'\s(?:>|/|\\|\|)\s')

DESCRIPTION_KINDS = {'descricao', 'descricao_curta', 'descricao_complementar', 'nome_apoio'}
CODE_KINDS = {'codigo', 'id_produto'}
PRICE_KINDS = {'preco_unitario', 'preco_custo'}
COMPATIBLE_KIND_GROUPS = [DESCRIPTION_KINDS, CODE_KINDS | {'gtin'}, PRICE_KINDS, {'ncm'}, {'fornecedor'}]


@dataclass(frozen=True)
class SemanticColumnProfile:
    column_name: str
    header_kind: str
    content_kind: str
    effective_kind: str
    confidence: float
    header_conflict: bool
    reason: str
    warning: str
    samples: tuple[str, ...]
    text: float
    numeric: float
    integer: float
    price: float
    gtin: float
    ncm: float
    url: float
    image: float
    breadcrumb: float
    avg_len: float
    unique: float
    has_values: bool


def _values(df: Any, column: str, limit: int = 120) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    result: list[str] = []
    try:
        series = df[column].dropna().astype(str)
    except Exception:
        return []
    for value in series.head(limit * 3):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null', '<na>'}:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _ratio(count: int, total: int) -> float:
    return round(count / max(total, 1), 4)


def _compact_number(value: str) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _looks_ncm(value: str, header_kind: str) -> bool:
    text = str(value or '').strip()
    digits = _compact_number(text)
    if len(digits) != 8:
        return False
    if header_kind == 'ncm':
        return True
    # Sem cabeçalho fiscal, número puro de 8 dígitos pode ser EAN-8/GTIN-8
    # ou código interno. Só aceite NCM automático quando houver separador fiscal.
    return text != digits and bool(NCM_RE.fullmatch(text))


def _kind_group(kind: str) -> set[str]:
    for group in COMPATIBLE_KIND_GROUPS:
        if kind in group:
            return set(group)
    return {kind}


def _kinds_compatible(a: str, b: str) -> bool:
    if not a or not b or a == 'custom' or b == 'custom':
        return True
    return bool(_kind_group(a) & _kind_group(b))


def _classify_content(*, header_kind: str, text: float, numeric: float, integer: float, price: float, gtin: float, ncm: float, url: float, image: float, breadcrumb: float, avg_len: float, unique: float, has_values: bool) -> tuple[str, float, str]:
    if not has_values:
        return 'custom', 0.0, 'Sem amostras preenchidas para validar o conteúdo.'
    if ncm >= 0.55:
        return 'ncm', min(0.99, 0.70 + ncm * 0.25), 'A maioria das amostras parece NCM.'
    if gtin >= 0.55:
        return 'gtin', min(0.99, 0.70 + gtin * 0.25), 'A maioria das amostras tem 8/12/13/14 dígitos compatíveis com GTIN/EAN.'
    if image >= 0.30:
        return 'imagem', min(0.98, 0.65 + image * 0.30), 'As amostras contêm URLs de imagem ou múltiplas imagens separadas.'
    if url >= 0.70:
        return 'url', min(0.97, 0.60 + url * 0.30), 'A maioria das amostras é URL/link.'
    if price >= 0.45:
        kind = 'preco_custo' if header_kind == 'preco_custo' else 'preco_unitario'
        return kind, min(0.97, 0.60 + price * 0.32), 'As amostras parecem valores monetários com centavos.'
    if integer >= 0.75 and price < 0.20 and avg_len <= 8:
        if header_kind in PRICE_KINDS:
            return header_kind, 0.58, 'Valores numéricos inteiros; mantido como preço apenas por indicação forte do cabeçalho.'
        return 'estoque', min(0.94, 0.55 + integer * 0.35), 'As amostras são números inteiros curtos, compatíveis com saldo/quantidade.'
    if breadcrumb >= 0.25 and text >= 0.40:
        return 'categoria', min(0.93, 0.55 + breadcrumb * 0.35), 'As amostras parecem caminho de categoria/departamento.'
    if text >= 0.50 and avg_len >= 12 and url < 0.20:
        return 'descricao', min(0.95, 0.50 + text * 0.25 + min(avg_len, 80) / 400), 'As amostras têm texto descritivo compatível com nome/descrição de produto.'
    if text >= 0.45 and avg_len <= 35 and numeric < 0.20 and url < 0.10:
        if unique <= 0.75 or header_kind in {'marca', 'fornecedor'}:
            kind = 'fornecedor' if header_kind == 'fornecedor' else 'marca'
            return kind, min(0.90, 0.50 + text * 0.25 + (0.10 if unique <= 0.75 else 0)), 'As amostras são textos curtos recorrentes, compatíveis com marca/fornecedor.'
    if numeric >= 0.65:
        return 'codigo', min(0.86, 0.45 + numeric * 0.30), 'As amostras são majoritariamente numéricas, mas sem assinatura forte de preço, GTIN, NCM ou estoque.'
    if text >= 0.30:
        return header_kind if header_kind != 'custom' else 'descricao', 0.50, 'Conteúdo textual genérico; cabeçalho usado apenas como apoio.'
    return header_kind if header_kind != 'custom' else 'custom', 0.35, 'Conteúdo inconclusivo; cabeçalho usado com baixa confiança.'


def analyze_column_semantics(df: Any, column: str, *, limit: int = 120) -> SemanticColumnProfile:
    column_name = str(column or '')
    values = _values(df, column_name, limit=limit)
    total = max(len(values), 1)
    header_kind = infer_kind(column_name)
    text = _ratio(sum(1 for value in values if TEXT_RE.search(value)), total)
    numeric = _ratio(sum(1 for value in values if NUMBER_RE.match(value.replace(' ', ''))), total)
    integer = _ratio(sum(1 for value in values if INTEGER_RE.match(value.replace(' ', ''))), total)
    price = _ratio(sum(1 for value in values if PRICE_RE.search(value)), total)
    ncm = _ratio(sum(1 for value in values if _looks_ncm(value, header_kind)), total)
    gtin = _ratio(sum(1 for value in values if GTIN_RE.match(_compact_number(value)) and not _looks_ncm(value, header_kind)), total)
    url = _ratio(sum(1 for value in values if URL_RE.search(value)), total)
    image = _ratio(sum(1 for value in values if URL_RE.search(value) and (IMAGE_RE.search(value) or '|' in value)), total)
    breadcrumb = _ratio(sum(1 for value in values if BREADCRUMB_RE.search(value)), total)
    avg_len = round(sum(len(value) for value in values) / total, 4)
    unique = round(len(set(value.lower() for value in values)) / total, 4) if values else 0.0
    content_kind, confidence, reason = _classify_content(header_kind=header_kind, text=text, numeric=numeric, integer=integer, price=price, gtin=gtin, ncm=ncm, url=url, image=image, breadcrumb=breadcrumb, avg_len=avg_len, unique=unique, has_values=bool(values))
    header_conflict = bool(header_kind != 'custom' and content_kind != 'custom' and not _kinds_compatible(header_kind, content_kind) and confidence >= 0.55)
    effective_kind = content_kind if content_kind != 'custom' and confidence >= 0.50 else header_kind
    warning = f'Cabeçalho sugere {header_kind}, mas as linhas parecem {content_kind}. Revisar antes de aceitar automático.' if header_conflict else ''
    return SemanticColumnProfile(column_name=column_name, header_kind=header_kind, content_kind=content_kind, effective_kind=effective_kind, confidence=round(float(confidence), 4), header_conflict=header_conflict, reason=reason, warning=warning, samples=tuple(values[:5]), text=text, numeric=numeric, integer=integer, price=price, gtin=gtin, ncm=ncm, url=url, image=image, breadcrumb=breadcrumb, avg_len=avg_len, unique=unique, has_values=bool(values))


def profile_as_mapping(df: Any, column: str, *, limit: int = 120) -> dict[str, Any]:
    profile = analyze_column_semantics(df, column, limit=limit)
    data = asdict(profile)
    data['kind'] = profile.effective_kind
    return data


__all__ = ['SemanticColumnProfile', 'analyze_column_semantics', 'profile_as_mapping']
