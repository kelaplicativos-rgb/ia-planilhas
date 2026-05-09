from __future__ import annotations

import re

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.text import normalize_key

TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,6}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
URL_RE = re.compile(r'^https?://', re.I)


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
    text = sum(1 for value in values if TEXT_RE.search(value)) / total
    numeric = sum(1 for value in values if re.fullmatch(r'\d+(?:[\.,]\d+)?', value.replace(' ', ''))) / total
    price = sum(1 for value in values if PRICE_RE.search(value)) / total
    gtin = sum(1 for value in values if GTIN_RE.match(re.sub(r'\D+', '', value))) / total
    url = sum(1 for value in values if URL_RE.search(value)) / total
    image = sum(1 for value in values if 'http' in value.lower() and any(ext in value.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '|'])) / total
    avg_len = sum(len(value) for value in values) / total
    return {
        'kind': infer_kind(column),
        'text': text,
        'numeric': numeric,
        'price': price,
        'gtin': gtin,
        'url': url,
        'image': image,
        'avg_len': avg_len,
    }


def _name_score(target: str, source: str) -> int:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if not target_key or not source_key:
        return 0
    if target_key == source_key:
        return 100
    score = 0
    if target_key in source_key or source_key in target_key:
        score += 45
    score += len(set(target_key.split()) & set(source_key.split())) * 15
    if infer_kind(target) == infer_kind(source) and infer_kind(target) != 'custom':
        score += 45
    return score


def _compatible(target: str, profile: dict[str, float | str]) -> bool:
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


def _content_score(target: str, profile: dict[str, float | str]) -> int:
    if not _compatible(target, profile):
        return 0
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
    return 18


def confidence_for_mapping(df_source: pd.DataFrame, target: str, source: str) -> dict[str, object]:
    if not source or not isinstance(df_source, pd.DataFrame) or source not in df_source.columns:
        return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': 'alterar', 'order': 0}
    profile = _profile(df_source, source)
    if not _compatible(target, profile):
        return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': 'alterar', 'order': 0}
    score = _name_score(target, source) + _content_score(target, profile)
    if score >= 115:
        return {'score': score, 'level': 'verde', 'emoji': '🟢', 'label': '100% seguro', 'order': 2}
    if score >= 82:
        return {'score': score, 'level': 'amarelo', 'emoji': '🟡', 'label': 'atenção', 'order': 1}
    return {'score': score, 'level': 'vermelho', 'emoji': '🔴', 'label': 'alterar', 'order': 0}


def confidence_for_mapping_dict(df_source: pd.DataFrame, mapping: dict[str, str]) -> dict[str, dict[str, object]]:
    return {target: confidence_for_mapping(df_source, target, source) for target, source in dict(mapping or {}).items()}


def sort_targets_by_confidence(target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    def key(target: str) -> tuple[int, int, str]:
        info = confidence.get(target, {}) if isinstance(confidence, dict) else {}
        return (int(info.get('order', 0) or 0), int(info.get('score', 0) or 0), normalize_key(target))
    return sorted([str(column) for column in target_columns], key=key)
