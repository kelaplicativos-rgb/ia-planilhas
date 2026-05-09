from __future__ import annotations

import re

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.text import normalize_key

TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,6}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
URL_RE = re.compile(r'^https?://', re.I)

CUSTOM_EQUIVALENT_TERMS = {
    'cest': ['cest'],
    'classe enquadramento ipi': ['classe enquadramento ipi', 'classe de enquadramento do ipi', 'enquadramento ipi'],
    'clonar dados pai': ['clonar dados pai', 'clonar dados do pai'],
    'codigo fornecedor': ['codigo fornecedor', 'cod fornecedor', 'cód no fornecedor', 'codigo no fornecedor', 'cód fornecedor'],
    'cross docking': ['cross docking', 'cross-docking'],
    'fornecedor': ['fornecedor', 'supplier'],
    'frete gratis': ['frete gratis', 'frete grátis'],
    'origem': ['origem'],
    'garantia': ['garantia'],
    'unidade': ['unidade', 'un'],
}


def resolved_empty_confidence() -> dict[str, object]:
    return {'score': 100, 'level': 'verde', 'emoji': '🟢', 'label': 'vazio confirmado', 'order': 2}


def pending_confidence() -> dict[str, object]:
    return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': 'precisa escolher', 'order': 0}


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
        'has_values': bool(values),
    }


def _compact_key(value: str) -> str:
    return normalize_key(value).replace(' ', '').replace('-', '')


def _custom_equivalent(target: str, source: str) -> bool:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    target_compact = _compact_key(target)
    source_compact = _compact_key(source)

    if target_compact and source_compact and target_compact == source_compact:
        return True

    for aliases in CUSTOM_EQUIVALENT_TERMS.values():
        normalized_aliases = [normalize_key(alias) for alias in aliases]
        target_hit = target_key in normalized_aliases
        source_hit = source_key in normalized_aliases
        if target_hit and source_hit:
            return True
    return False


def _exact_normalized_match(target: str, source: str) -> bool:
    return bool(_compact_key(target) and _compact_key(target) == _compact_key(source))


def _manual_like_valid(target: str, source: str, profile: dict[str, float | str]) -> bool:
    if _custom_equivalent(target, source):
        return True

    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or infer_kind(source))
    has_values = bool(profile.get('has_values'))
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)

    if target_kind != 'custom' and target_kind == source_kind:
        return True
    if target_kind in {'codigo', 'id_produto'}:
        return has_values and (source_kind in {'codigo', 'id_produto', 'gtin'} or gtin >= 0.30 or numeric >= 0.45 or text >= 0.35)
    if target_kind == 'gtin':
        return gtin >= 0.45 or source_kind == 'gtin'
    if target_kind in {'descricao', 'nome_apoio'}:
        return has_values and text >= 0.35 and avg_len >= 4 and url < 0.35
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return price >= 0.25 or numeric >= 0.55
    if target_kind == 'estoque':
        return numeric >= 0.55 or source_kind == 'estoque'
    if target_kind == 'url':
        return url >= 0.40 or source_kind == 'url'
    if target_kind == 'imagem':
        return image >= 0.25 or source_kind == 'imagem'
    if target_kind == 'marca':
        return has_values and text >= 0.30 and avg_len <= 45 and url == 0
    if target_kind == 'categoria':
        return has_values and text >= 0.25 and avg_len <= 120

    return has_values


def _name_score(target: str, source: str) -> int:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if not target_key or not source_key:
        return 0
    if _custom_equivalent(target, source):
        return 120
    score = 0
    if target_key in source_key or source_key in target_key:
        score += 55
    score += len(set(target_key.split()) & set(source_key.split())) * 18
    if infer_kind(target) == infer_kind(source) and infer_kind(target) != 'custom':
        score += 50
    return score


def _compatible(target: str, source: str, profile: dict[str, float | str]) -> bool:
    return _manual_like_valid(target, source, profile)


def _content_score(target: str, source: str, profile: dict[str, float | str]) -> int:
    if not _compatible(target, source, profile):
        return 0
    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or infer_kind(source))
    if _custom_equivalent(target, source):
        return 35
    if target_kind == source_kind and target_kind != 'custom':
        return 45
    if target_kind == 'gtin':
        return int(float(profile.get('gtin') or 0) * 45)
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(float(profile.get('price') or 0), float(profile.get('numeric') or 0)) * 35)
    if target_kind in {'descricao', 'nome_apoio'}:
        return int(float(profile.get('text') or 0) * 30 + min(float(profile.get('avg_len') or 0), 80) / 4)
    if target_kind == 'custom':
        return 25
    return 18


def _confidence(score: int, level_hint: str = '') -> dict[str, object]:
    if level_hint == 'verde':
        return {'score': max(score, 100), 'level': 'verde', 'emoji': '🟢', 'label': 'pronto', 'order': 2}
    if score >= 82:
        return {'score': score, 'level': 'amarelo', 'emoji': '🟡', 'label': 'conferir', 'order': 1}
    return pending_confidence()


def confidence_for_mapping(df_source: pd.DataFrame, target: str, source: str) -> dict[str, object]:
    if not source:
        return pending_confidence()

    if not isinstance(df_source, pd.DataFrame) or source not in df_source.columns:
        return pending_confidence()

    profile = _profile(df_source, source)
    if not _compatible(target, source, profile):
        return pending_confidence()

    score = _name_score(target, source) + _content_score(target, source, profile)

    if _exact_normalized_match(target, source):
        return _confidence(score, 'verde')

    return _confidence(score)


def confidence_for_mapping_dict(df_source: pd.DataFrame, mapping: dict[str, str]) -> dict[str, dict[str, object]]:
    return {target: confidence_for_mapping(df_source, target, source) for target, source in dict(mapping or {}).items()}


def sort_targets_by_confidence(target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    def key(target: str) -> tuple[int, int, str]:
        info = confidence.get(target, {}) if isinstance(confidence, dict) else {}
        return (int(info.get('order', 0) or 0), int(info.get('score', 0) or 0), normalize_key(target))
    return sorted([str(column) for column in target_columns], key=key)
