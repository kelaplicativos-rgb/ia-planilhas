from __future__ import annotations

import re

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.text import normalize_key

TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,6}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
NUMBER_RE = re.compile(r'^-?\d+(?:[\.,]\d+)?$')
URL_RE = re.compile(r'https?://', re.I)
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)', re.I)

FIELD_ALIASES = {
    'codigo': ['codigo', 'código', 'cod', 'sku', 'referencia', 'referência', 'ref', 'id produto', 'id'],
    'id_produto': ['id produto', 'codigo produto', 'código produto', 'id', 'sku', 'referencia', 'referência'],
    'descricao': ['descricao', 'descrição', 'nome', 'produto', 'titulo', 'título', 'title', 'nome produto'],
    'nome_apoio': ['nome', 'produto', 'titulo', 'título', 'descricao', 'descrição'],
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
    'fornecedor': ['fornecedor', 'supplier', 'nome fornecedor', 'nome do fornecedor'],
    'observacao': ['observacao', 'observação', 'obs', 'detalhes', 'informacoes', 'informações'],
}

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

PRICE_SOURCE_TERMS = ['preco', 'preço', 'valor', 'price', 'custo', 'venda', 'unitario', 'unitário']


def resolved_empty_confidence() -> dict[str, object]:
    return {'score': 100, 'level': 'verde', 'emoji': '🟢', 'label': 'vazio confirmado', 'order': 2, 'strict': True}


def pending_confidence() -> dict[str, object]:
    return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': 'precisa escolher', 'order': 0, 'strict': False}


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


def _profile(df: pd.DataFrame, column: str) -> dict[str, float | str | bool]:
    values = _values(df, column)
    total = max(len(values), 1)
    text = sum(1 for value in values if TEXT_RE.search(value)) / total
    numeric = sum(1 for value in values if NUMBER_RE.match(value.replace(' ', ''))) / total
    price = sum(1 for value in values if PRICE_RE.search(value)) / total
    gtin = sum(1 for value in values if GTIN_RE.match(re.sub(r'\D+', '', value))) / total
    url = sum(1 for value in values if URL_RE.search(value)) / total
    image = sum(1 for value in values if URL_RE.search(value) and (IMAGE_RE.search(value) or '|' in value)) / total
    avg_len = sum(len(value) for value in values) / total
    unique = len(set(value.lower() for value in values)) / total if values else 0
    return {
        'kind': infer_kind(column),
        'text': text,
        'numeric': numeric,
        'price': price,
        'gtin': gtin,
        'url': url,
        'image': image,
        'avg_len': avg_len,
        'unique': unique,
        'has_values': bool(values),
    }


def _compact_key(value: str) -> str:
    return normalize_key(value).replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('/', '')


def _target_kind(target: str) -> str:
    kind = infer_kind(target)
    if kind != 'custom':
        return kind
    target_key = normalize_key(target)
    for kind_name, aliases in FIELD_ALIASES.items():
        if any(normalize_key(alias) in target_key or target_key in normalize_key(alias) for alias in aliases):
            return kind_name
    return 'custom'


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


def _bit_to_bit_match(target: str, source: str) -> bool:
    return str(target) == str(source)


def _alias_score(target_kind: str, source: str) -> int:
    source_key = normalize_key(source)
    score = 0
    for alias in FIELD_ALIASES.get(target_kind, []):
        alias_key = normalize_key(alias)
        if alias_key and (alias_key in source_key or source_key in alias_key):
            score += 40
    return min(score, 80)


def _name_score(target: str, source: str) -> int:
    target_kind = _target_kind(target)
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if not target_key or not source_key:
        return 0

    if _custom_equivalent(target, source):
        return 150

    score = 0
    if target_key == source_key or _compact_key(target) == _compact_key(source):
        score += 120
    elif target_key in source_key or source_key in target_key:
        score += 45
    score += len(set(target_key.split()) & set(source_key.split())) * 14
    score += _alias_score(target_kind, source)
    if infer_kind(source) == target_kind and target_kind != 'custom':
        score += 45
    return score


def _is_price_like_source(source: str, profile: dict[str, float | str | bool]) -> bool:
    source_key = normalize_key(source)
    if str(profile.get('kind') or '') in {'preco_unitario', 'preco_custo'}:
        return True
    return any(normalize_key(term) in source_key for term in PRICE_SOURCE_TERMS)


def _content_score(target: str, source: str, profile: dict[str, float | str | bool]) -> int:
    target_kind = _target_kind(target)
    source_kind = str(profile.get('kind') or infer_kind(source))
    has_values = bool(profile.get('has_values'))
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)
    unique = float(profile.get('unique') or 0)

    if not has_values:
        return -80
    if target_kind == source_kind and target_kind != 'custom':
        return 70
    if target_kind in {'codigo', 'id_produto'}:
        return 45 if gtin >= 0.30 or numeric >= 0.55 or source_kind in {'codigo', 'id_produto', 'gtin'} else -80
    if target_kind == 'gtin':
        return int(gtin * 110) if gtin >= 0.50 or source_kind == 'gtin' else -120
    if target_kind in {'descricao', 'nome_apoio'}:
        return int(text * 55 + min(avg_len, 80) / 3) if text >= 0.40 and url < 0.25 else -80
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(price, numeric) * 90) if price >= 0.25 or numeric >= 0.70 else -90
    if target_kind == 'estoque':
        if _is_price_like_source(source, profile):
            return -120
        return int(numeric * 90) if numeric >= 0.60 and price < 0.35 else -80
    if target_kind == 'url':
        return int(url * 95) if url >= 0.45 or source_kind == 'url' else -90
    if target_kind == 'imagem':
        return int(image * 110) if image >= 0.30 or source_kind == 'imagem' else -120
    if target_kind == 'marca':
        return int(text * 55 + (30 if avg_len <= 45 else -20)) if text >= 0.30 and url == 0 else -70
    if target_kind == 'categoria':
        return int(text * 50 + (25 if avg_len <= 140 else 0)) if text >= 0.25 else -60
    if target_kind == 'fornecedor':
        return 60 if text >= 0.60 and numeric < 0.10 and url == 0 and avg_len <= 45 and unique <= 0.70 else -90
    if target_kind == 'custom':
        return 30 if has_values else -30
    return -30


def _compatible(target: str, source: str, profile: dict[str, float | str | bool]) -> bool:
    return _content_score(target, source, profile) > -70 or _name_score(target, source) >= 100


def _confidence(score: int, level_hint: str = '') -> dict[str, object]:
    if level_hint == 'verde':
        return {'score': 100, 'level': 'verde', 'emoji': '🟢', 'label': '100% bit a bit', 'order': 2, 'strict': True}

    safe_score = min(max(int(score), 0), 99)
    if safe_score >= 130:
        return {'score': safe_score, 'level': 'verde', 'emoji': '🟢', 'label': 'sugestão forte por cabeçalho e conteúdo', 'order': 2, 'strict': False}
    if safe_score >= 82:
        return {'score': safe_score, 'level': 'amarelo', 'emoji': '🟡', 'label': 'conferir sugestão', 'order': 1, 'strict': False}
    return pending_confidence()


def confidence_for_mapping(df_source: pd.DataFrame, target: str, source: str) -> dict[str, object]:
    if not source:
        return pending_confidence()

    if not isinstance(df_source, pd.DataFrame) or source not in df_source.columns:
        return pending_confidence()

    profile = _profile(df_source, source)
    if not _compatible(target, source, profile):
        return pending_confidence()

    if _bit_to_bit_match(target, source):
        return _confidence(100, 'verde')

    score = _name_score(target, source) + _content_score(target, source, profile)
    return _confidence(score)


def confidence_for_mapping_dict(df_source: pd.DataFrame, mapping: dict[str, str]) -> dict[str, dict[str, object]]:
    return {target: confidence_for_mapping(df_source, target, source) for target, source in dict(mapping or {}).items()}


def sort_targets_by_confidence(target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    def key(target: str) -> tuple[int, int, str]:
        info = confidence.get(target, {}) if isinstance(confidence, dict) else {}
        return (int(info.get('order', 0) or 0), int(info.get('score', 0) or 0), normalize_key(target))
    return sorted([str(column) for column in target_columns], key=key)
