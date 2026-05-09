from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.mapping import auto_map_columns
from bling_app_zero.core.mapping_confidence import confidence_for_mapping
from bling_app_zero.core.text import normalize_key

PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,7}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
NUMBER_RE = re.compile(r'^\d+(?:[\.,]\d+)?$')
URL_RE = re.compile(r'https?://', re.I)
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)', re.I)

FIELD_ALIASES = {
    'codigo': ['codigo', 'código', 'cod', 'sku', 'referencia', 'referência', 'ref', 'id produto', 'id', 'produto id'],
    'id_produto': ['id produto', 'codigo produto', 'código produto', 'id', 'sku', 'referencia'],
    'descricao': ['descricao', 'descrição', 'nome', 'produto', 'titulo', 'título', 'title', 'nome produto'],
    'nome_apoio': ['nome', 'produto', 'titulo', 'descrição', 'descricao'],
    'preco_unitario': ['preco', 'preço', 'valor', 'venda', 'preco venda', 'preço venda', 'preco unitario', 'preço unitário', 'price'],
    'preco_custo': ['custo', 'preco custo', 'preço custo', 'valor custo', 'cost'],
    'estoque': ['estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'balanço', 'stock', 'inventory'],
    'gtin': ['gtin', 'ean', 'codigo barras', 'código barras', 'codigo de barras', 'código de barras', 'barcode'],
    'marca': ['marca', 'brand', 'fabricante', 'manufacturer'],
    'categoria': ['categoria', 'category', 'departamento', 'breadcrumb', 'grupo', 'familia', 'família'],
    'imagem': ['imagem', 'imagens', 'foto', 'fotos', 'image', 'images', 'url imagem', 'url foto'],
    'url': ['url', 'link', 'pagina', 'página', 'site', 'produto url'],
    'ncm': ['ncm'],
    'deposito': ['deposito', 'depósito', 'local estoque', 'almoxarifado'],
    'observacao': ['observacao', 'observação', 'obs', 'detalhes', 'informacoes', 'informações'],
    'custom': [
        'cest', 'ipi', 'classe enquadramento ipi', 'classe de enquadramento do ipi',
        'cross docking', 'cross-docking', 'frete gratis', 'frete grátis', 'garantia',
        'origem', 'unidade', 'peso bruto', 'peso liquido', 'peso líquido', 'altura',
        'largura', 'profundidade', 'comprimento', 'volumes', 'situacao', 'situação',
        'fornecedor', 'codigo fornecedor', 'código fornecedor', 'cód no fornecedor',
    ],
}

RISKY_TARGET_TERMS = [
    'altura', 'largura', 'profundidade', 'peso', 'comprimento', 'unidade', 'origem',
    'cest', 'ipi', 'classe enquadramento', 'cross docking', 'clonar dados', 'frete gratis',
    'frete grátis', 'garantia', 'condicao', 'condição', 'situacao', 'situação', 'tipo item',
]

PRICE_SOURCE_TERMS = ['preco', 'preço', 'valor', 'price', 'custo', 'venda', 'unitario', 'unitário']

SAFE_CONSTANTS = {
    'clonar dados do pai': 'NÃO',
    'cross docking': '0',
    'frete gratis': 'NÃO',
    'frete grátis': 'NÃO',
}


@dataclass(frozen=True)
class Candidate:
    source: str
    score: int


def _compact(value: str) -> str:
    return normalize_key(value).replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('/', '')


def _is_exact_or_equivalent(target: str, source: str) -> bool:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if target_key and source_key and target_key == source_key:
        return True
    target_compact = _compact(target)
    source_compact = _compact(source)
    return bool(target_compact and source_compact and target_compact == source_compact)


def _values(df: pd.DataFrame, column: str, limit: int = 80) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values: list[str] = []
    for value in df[column].dropna().astype(str).head(limit * 2):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null'}:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def _profile(df: pd.DataFrame, column: str) -> dict[str, float | str]:
    values = _values(df, column)
    total = max(len(values), 1)
    return {
        'kind': infer_kind(column),
        'name': column,
        'text': sum(1 for v in values if re.search(r'[A-Za-zÀ-ÿ]{3,}', v)) / total,
        'numeric': sum(1 for v in values if NUMBER_RE.match(v.replace(' ', ''))) / total,
        'price': sum(1 for v in values if PRICE_RE.search(v)) / total,
        'gtin': sum(1 for v in values if GTIN_RE.match(re.sub(r'\D+', '', v))) / total,
        'url': sum(1 for v in values if URL_RE.search(v)) / total,
        'image': sum(1 for v in values if URL_RE.search(v) and (IMAGE_RE.search(v) or '|' in v)) / total,
        'avg_len': sum(len(v) for v in values) / total,
        'unique': len(set(v.lower() for v in values)) / total,
        'has_values': bool(values),
    }


def _target_kind(target: str) -> str:
    kind = infer_kind(target)
    if kind != 'custom':
        return kind
    target_key = normalize_key(target)
    for kind_name, aliases in FIELD_ALIASES.items():
        if any(normalize_key(alias) in target_key or target_key in normalize_key(alias) for alias in aliases):
            return kind_name
    return 'custom'


def _is_risky_target(target: str) -> bool:
    key = normalize_key(target)
    return any(term in key for term in RISKY_TARGET_TERMS)


def _is_price_like_source(source: str, profile: dict[str, float | str]) -> bool:
    source_key = normalize_key(source)
    if str(profile.get('kind') or '') in {'preco_unitario', 'preco_custo'}:
        return True
    return any(normalize_key(term) in source_key for term in PRICE_SOURCE_TERMS)


def _name_score(target: str, source: str, target_kind: str) -> int:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    score = 0
    if _is_exact_or_equivalent(target, source):
        score += 180
    if target_key and source_key and (target_key in source_key or source_key in target_key):
        score += 45
    score += len(set(target_key.split()) & set(source_key.split())) * 12
    for alias in FIELD_ALIASES.get(target_kind, []):
        alias_key = normalize_key(alias)
        if alias_key and (alias_key in source_key or source_key in alias_key):
            score += 55
    if infer_kind(source) == target_kind and target_kind != 'custom':
        score += 45
    return score


def _content_score(target_kind: str, source: str, profile: dict[str, float | str], exact_match: bool = False) -> int:
    if exact_match:
        return 80

    source_kind = str(profile.get('kind') or '')
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)
    unique = float(profile.get('unique') or 0)
    has_values = bool(profile.get('has_values'))

    if target_kind == source_kind and target_kind != 'custom':
        return 60
    if target_kind == 'custom':
        return 25 if has_values else 5
    if target_kind in {'codigo', 'id_produto'}:
        return 45 if gtin >= 0.40 or numeric >= 0.60 or source_kind in {'codigo', 'gtin'} else -80
    if target_kind == 'gtin':
        return int(gtin * 100) if gtin >= 0.50 else -100
    if target_kind in {'descricao', 'nome_apoio'}:
        return int(text * 50 + min(avg_len, 80) / 3) if text >= 0.45 and url < 0.25 else -80
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(price, numeric) * 80) if price >= 0.25 or numeric >= 0.70 else -80
    if target_kind == 'estoque':
        if _is_price_like_source(source, profile):
            return -120
        return int(numeric * 80) if numeric >= 0.65 and price < 0.35 else -80
    if target_kind == 'url':
        return int(url * 90) if url >= 0.45 else -80
    if target_kind == 'imagem':
        return int(image * 100) if image >= 0.30 else -100
    if target_kind == 'marca':
        return int(text * 50 + (30 if avg_len <= 35 else -20)) if text >= 0.35 and url == 0 else -70
    if target_kind == 'categoria':
        return int(text * 50 + (25 if avg_len <= 90 else 0)) if text >= 0.35 else -60
    if target_kind == 'deposito':
        return 40 if text >= 0.30 and unique <= 0.30 else -50
    return -30


def _best_candidate(df: pd.DataFrame, target: str, source_columns: list[str], used: set[str]) -> Candidate:
    target_kind = _target_kind(target)

    for source in source_columns:
        if source in used:
            continue
        if _is_exact_or_equivalent(target, source):
            return Candidate(source, 260)

    if _is_risky_target(target):
        return Candidate('', 0)

    best = Candidate('', 0)
    for source in source_columns:
        if source in used:
            continue
        profile = _profile(df, source)
        exact = _is_exact_or_equivalent(target, source)
        score = _name_score(target, source, target_kind) + _content_score(target_kind, source, profile, exact)
        if score > best.score:
            best = Candidate(source, score)
    return best


def _force_exact_matches_first(mapping: dict[str, str], source_columns: list[str], target_columns: list[str]) -> dict[str, str]:
    out = dict(mapping or {})
    used = {value for value in out.values() if value}
    for target in target_columns:
        current = out.get(target, '')
        if current and _is_exact_or_equivalent(target, current):
            continue
        for source in source_columns:
            if source in used and source != current:
                continue
            if _is_exact_or_equivalent(target, source):
                if current:
                    used.discard(current)
                out[target] = source
                used.add(source)
                break
    return out


def super_auto_map_columns(df_source: pd.DataFrame, df_model: pd.DataFrame, min_score: int = 80) -> dict[str, str]:
    base_mapping = auto_map_columns(df_source, df_model)
    if not isinstance(df_source, pd.DataFrame) or not isinstance(df_model, pd.DataFrame):
        return base_mapping

    source_columns = [str(c) for c in df_source.columns]
    target_columns = [str(c) for c in df_model.columns]
    mapping = _force_exact_matches_first(base_mapping, source_columns, target_columns)
    used = {source for source in mapping.values() if source}

    for target in target_columns:
        current = mapping.get(target, '')
        if current:
            if _is_exact_or_equivalent(target, current):
                continue
            info = confidence_for_mapping(df_source, target, current)
            if str(info.get('level')) in {'verde', 'amarelo'}:
                continue
            used.discard(current)

        candidate = _best_candidate(df_source, target, source_columns, used)
        if candidate.source and candidate.score >= min_score:
            mapping[target] = candidate.source
            used.add(candidate.source)
        elif not current:
            mapping[target] = ''

    return mapping


def safe_default_for_target(target: str) -> str:
    key = normalize_key(target)
    for term, value in SAFE_CONSTANTS.items():
        if term in key:
            return value
    return ''
