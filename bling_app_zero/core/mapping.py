from __future__ import annotations

import re

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.text import normalize_key

SYNONYMS = {
    'codigo': ['codigo', 'cod', 'sku', 'referencia', 'id produto', 'ref'],
    'descricao': ['descricao', 'nome', 'produto', 'titulo', 'title'],
    'descricao curta': ['descricao curta', 'resumo', 'complementar'],
    'preco': ['preco', 'valor', 'preco venda', 'preco unitario', 'price'],
    'estoque': ['estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'stock'],
    'gtin': ['gtin', 'ean', 'codigo barras', 'codigo de barras', 'barcode'],
    'marca': ['marca', 'fabricante', 'brand'],
    'categoria': ['categoria', 'departamento', 'breadcrumb', 'category'],
    'imagem': ['imagem', 'imagens', 'foto', 'fotos', 'url imagem', 'url imagens', 'image'],
    'deposito': ['deposito', 'almoxarifado', 'local estoque'],
    'ncm': ['ncm'],
}

GENERIC_DESCRIPTION_TARGETS = {'descricao complementar', 'descricao curta'}
TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,6}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
URL_RE = re.compile(r'^https?://', re.I)


def _score(target: str, source: str) -> int:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if not target_key or not source_key:
        return 0
    if target_key == source_key:
        return 100
    score = 0
    if target_key in source_key or source_key in target_key:
        score += 45
    target_tokens = set(target_key.split())
    source_tokens = set(source_key.split())
    score += len(target_tokens & source_tokens) * 15
    for family, names in SYNONYMS.items():
        fam = normalize_key(family)
        if fam in target_key:
            for synonym in names:
                if normalize_key(synonym) in source_key:
                    score += 35
    return score


def _values(df: pd.DataFrame, column: str, limit: int = 80) -> list[str]:
    result: list[str] = []
    if column not in df.columns:
        return result
    for value in df[column].dropna().astype(str).head(limit * 2):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null'}:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _ratio(count: int, total: int) -> float:
    return count / max(total, 1)


def _content_profile(df: pd.DataFrame, column: str) -> dict[str, float | str]:
    vals = _values(df, column)
    total = max(len(vals), 1)
    text_count = sum(1 for v in vals if TEXT_RE.search(v))
    numeric_count = sum(1 for v in vals if re.fullmatch(r'\d+(?:[\.,]\d+)?', v.replace(' ', '')))
    price_count = sum(1 for v in vals if PRICE_RE.search(v))
    gtin_count = sum(1 for v in vals if GTIN_RE.match(re.sub(r'\D+', '', v)))
    url_count = sum(1 for v in vals if URL_RE.search(v))
    image_count = sum(1 for v in vals if 'http' in v.lower() and any(ext in v.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '|']))
    avg_len = sum(len(v) for v in vals) / total
    return {
        'kind': infer_kind(column),
        'text': _ratio(text_count, total),
        'numeric': _ratio(numeric_count, total),
        'price': _ratio(price_count, total),
        'gtin': _ratio(gtin_count, total),
        'url': _ratio(url_count, total),
        'image': _ratio(image_count, total),
        'avg_len': avg_len,
    }


def _compatible(target: str, profile: dict[str, float | str]) -> bool:
    target_key = normalize_key(target)
    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or '')
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)

    if target_kind == 'custom':
        return False
    if target_key in GENERIC_DESCRIPTION_TARGETS and source_kind != target_kind:
        return False
    if target_kind in {'codigo', 'id_produto'}:
        return source_kind in {'codigo', 'id_produto', 'gtin'} or gtin >= 0.45 or numeric >= 0.70
    if target_kind == 'gtin':
        return source_kind == 'gtin' or gtin >= 0.55
    if target_kind in {'descricao', 'nome_apoio'}:
        return source_kind in {'descricao', 'nome_apoio'} or (text >= 0.55 and avg_len >= 8 and url < 0.20)
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return source_kind in {'preco_unitario', 'preco_custo'} or price >= 0.35 or numeric >= 0.70
    if target_kind == 'estoque':
        return source_kind == 'estoque' or numeric >= 0.80
    if target_kind == 'url':
        return source_kind == 'url' or url >= 0.60
    if target_kind == 'imagem':
        return source_kind == 'imagem' or image >= 0.35
    if target_kind == 'marca':
        return source_kind == 'marca' or (text >= 0.45 and avg_len <= 35 and url == 0)
    if target_kind == 'categoria':
        return source_kind == 'categoria' or (text >= 0.40 and avg_len <= 90)
    return source_kind == target_kind


def _content_bonus(target: str, profile: dict[str, float | str]) -> int:
    if not _compatible(target, profile):
        return -1000
    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or '')
    if target_kind == source_kind and target_kind != 'custom':
        return 45
    if target_kind == 'gtin':
        return int(float(profile.get('gtin') or 0) * 45)
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(float(profile.get('price') or 0), float(profile.get('numeric') or 0)) * 35)
    if target_kind in {'descricao', 'nome_apoio'}:
        return int(float(profile.get('text') or 0) * 30 + min(float(profile.get('avg_len') or 0), 80) / 4)
    return 15


def auto_map_columns(df_source: pd.DataFrame, df_model: pd.DataFrame) -> dict[str, str]:
    if df_source is None or df_model is None or df_source.empty and len(df_source.columns) == 0:
        return {}

    source_cols = [str(c) for c in df_source.columns]
    model_cols = [str(c) for c in df_model.columns]
    profiles = {source_col: _content_profile(df_source, source_col) for source_col in source_cols}
    used: set[str] = set()
    mapping: dict[str, str] = {}

    for model_col in model_cols:
        best_col = ''
        best_score = 0
        for source_col in source_cols:
            if source_col in used:
                continue
            base_score = _score(model_col, source_col)
            bonus = _content_bonus(model_col, profiles[source_col])
            if bonus <= -1000:
                continue
            score = base_score + bonus
            if score > best_score:
                best_score = score
                best_col = source_col
        if best_col and best_score >= 55:
            mapping[model_col] = best_col
            used.add(best_col)
        else:
            mapping[model_col] = ''

    return mapping


def apply_mapping(df_source: pd.DataFrame, df_model: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    if df_model is None or len(df_model.columns) == 0:
        return pd.DataFrame()
    if df_source is None or df_source.empty:
        return pd.DataFrame(columns=df_model.columns)

    out = pd.DataFrame(index=df_source.index)
    for model_col in df_model.columns:
        source_col = mapping.get(str(model_col), '') if isinstance(mapping, dict) else ''
        if source_col and source_col in df_source.columns:
            out[model_col] = df_source[source_col].fillna('').astype(str)
        else:
            out[model_col] = ''
    return out.fillna('')


def build_model_from_columns(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=[str(c) for c in columns])
