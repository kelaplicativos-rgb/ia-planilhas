from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.mapping_state import (
    CONFIDENCE_EMPTY,
    CONFIDENCE_HIGH,
    CONFIDENCE_REVIEW,
    EMPTY_OPTION,
    MappingField,
    MappingRequest,
    MappingState,
)
from bling_app_zero.core.smart_column_profiler import profile_as_mapping
from bling_app_zero.core.text import normalize_key as normalize_column_key

RESPONSIBLE_FILE = 'bling_app_zero/core/spreadsheet_mapping_center.py'

# -----------------------------------------------------------------------------
# Vocabulário central de campos/colunas de planilhas anexadas.
# -----------------------------------------------------------------------------
FIELD_ALIASES = {
    'codigo': ['codigo', 'código', 'cod', 'sku', 'referencia', 'referência', 'ref', 'id produto', 'id'],
    'id_produto': ['id produto', 'codigo produto', 'código produto', 'id', 'sku', 'referencia', 'referência'],
    'descricao': ['descricao', 'descrição', 'nome', 'produto', 'titulo', 'título', 'title', 'nome produto'],
    'nome_apoio': ['nome', 'produto', 'titulo', 'título', 'descricao', 'descrição'],
    'descricao curta': ['descricao curta', 'descrição curta', 'resumo', 'complementar'],
    'preco_unitario': ['preco', 'preço', 'valor', 'venda', 'preco venda', 'preço venda', 'preco unitario', 'preço unitário', 'price'],
    'preco_custo': ['custo', 'preco custo', 'preço custo', 'valor custo', 'cost'],
    'estoque': ['estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'balanço', 'stock', 'inventory'],
    'gtin': ['gtin', 'ean', 'codigo barras', 'código barras', 'codigo de barras', 'código de barras', 'barcode'],
    'marca': ['marca', 'brand', 'fabricante', 'manufacturer'],
    'categoria': ['categoria', 'category', 'departamento', 'breadcrumb', 'grupo', 'familia', 'família'],
    'imagem': ['imagem', 'imagens', 'foto', 'fotos', 'image', 'images', 'url imagem', 'url foto', 'url imagens'],
    'url': ['url', 'link', 'pagina', 'página', 'site', 'produto url', 'url produto'],
    'ncm': ['ncm'],
    'deposito': ['deposito', 'depósito', 'local estoque', 'almoxarifado'],
    'fornecedor': ['fornecedor', 'supplier', 'nome fornecedor', 'nome do fornecedor'],
    'observacao': ['observacao', 'observação', 'obs', 'detalhes', 'informacoes', 'informações'],
}

# Compatibilidade com o nome antigo de bling_app_zero.core.mapping.SYNONYMS.
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

GENERIC_DESCRIPTION_TARGETS = {'descricao complementar', 'descricao curta'}
PRICE_LIKE_TERMS = {'preco', 'preço', 'valor', 'price', 'custo', 'venda', 'unitario', 'unitário'}
PRICE_SOURCE_TERMS = ['preco', 'preço', 'valor', 'price', 'custo', 'venda', 'unitario', 'unitário']

TEXT_RE = re.compile(r'[A-Za-zÀ-ÿ]{3,}')
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,6}(?:[\.,]\d{2})')
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
NUMBER_RE = re.compile(r'^-?\d+(?:[\.,]\d+)?$')
URL_RE = re.compile(r'https?://', re.I)
URL_START_RE = re.compile(r'^https?://', re.I)
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)', re.I)


@dataclass(frozen=True)
class MappingCommandResult:
    state: MappingState
    rows: tuple[dict[str, str], ...]
    message: str = ''
    needs_rerun: bool = False


# -----------------------------------------------------------------------------
# Normalização e leitura de amostras.
# -----------------------------------------------------------------------------
def normalize_key(value: object) -> str:
    """Compatibilidade com o antigo core.mapping.normalize_key."""
    return normalize_column_key(str(value or ''))


def normalize_engine_key(value: object) -> str:
    """Compatibilidade com o antigo core.mapping_engine.normalize_key."""
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def _compact_key(value: object) -> str:
    return normalize_column_key(str(value or '')).replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('/', '')


def _values(df: pd.DataFrame, column: str, limit: int = 80) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    result: list[str] = []
    for value in df[column].dropna().astype(str).head(limit * 2):
        text = str(value or '').strip()
        if text and text.lower() not in {'nan', 'none', 'null'}:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _ratio(count: int, total: int) -> float:
    return count / max(total, 1)


def _legacy_profile(df: pd.DataFrame, column: str) -> dict[str, float | str | bool]:
    """Fallback antigo, mantido para evitar quebra caso o profiler novo falhe."""
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
        'header_kind': infer_kind(column),
        'content_kind': 'custom',
        'effective_kind': infer_kind(column),
        'confidence': 0.0,
        'header_conflict': False,
        'reason': '',
        'warning': '',
        'samples': tuple(values[:5]),
        'text': text,
        'numeric': numeric,
        'integer': numeric,
        'price': price,
        'gtin': gtin,
        'url': url,
        'image': image,
        'breadcrumb': 0.0,
        'avg_len': avg_len,
        'unique': unique,
        'has_values': bool(values),
    }


def _profile(df: pd.DataFrame, column: str) -> dict[str, float | str | bool | tuple[str, ...]]:
    """Perfil semântico: cabeçalho + conteúdo real das linhas.

    A chave ``kind`` agora representa o tipo efetivo validado pelo conteúdo,
    não apenas o tipo inferido pelo cabeçalho. Isso evita mapear, por exemplo,
    coluna chamada "Produto" contendo EAN para o campo Descrição.
    """
    try:
        return profile_as_mapping(df, column)
    except Exception:
        return _legacy_profile(df, column)


def _content_profile(df: pd.DataFrame, column: str) -> dict[str, float | str | bool | tuple[str, ...]]:
    profile = _profile(df, column)
    return {
        'kind': str(profile.get('kind') or ''),
        'header_kind': str(profile.get('header_kind') or ''),
        'content_kind': str(profile.get('content_kind') or ''),
        'effective_kind': str(profile.get('effective_kind') or profile.get('kind') or ''),
        'confidence': float(profile.get('confidence') or 0),
        'header_conflict': bool(profile.get('header_conflict')),
        'reason': str(profile.get('reason') or ''),
        'warning': str(profile.get('warning') or ''),
        'samples': tuple(profile.get('samples') or ()),
        'text': float(profile.get('text') or 0),
        'numeric': float(profile.get('numeric') or 0),
        'integer': float(profile.get('integer') or profile.get('numeric') or 0),
        'price': float(profile.get('price') or 0),
        'gtin': float(profile.get('gtin') or 0),
        'url': float(profile.get('url') or 0),
        'image': float(profile.get('image') or 0),
        'breadcrumb': float(profile.get('breadcrumb') or 0),
        'avg_len': float(profile.get('avg_len') or 0),
        'unique': float(profile.get('unique') or 0),
        'has_values': bool(profile.get('has_values')),
    }


def source_has_values(source: Any, source_column: str) -> bool:
    try:
        columns = getattr(source, 'columns', [])
        if source_column in columns:
            return bool(source[source_column].astype(str).str.strip().ne('').any())
    except Exception:
        pass
    return False


# -----------------------------------------------------------------------------
# Auto-mapeamento de planilha origem -> modelo destino.
# -----------------------------------------------------------------------------
def _score(target: str, source: str) -> int:
    target_key = normalize_column_key(target)
    source_key = normalize_column_key(source)
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
        fam = normalize_column_key(family)
        if fam in target_key:
            for synonym in names:
                if normalize_column_key(synonym) in source_key:
                    score += 35
    return score


def _source_has_price_name(column: str) -> bool:
    tokens = set(normalize_column_key(column).split())
    return bool(tokens & {normalize_column_key(term) for term in PRICE_LIKE_TERMS})


def _is_kind_compatible(target_kind: str, source_kind: str) -> bool:
    if not target_kind or not source_kind or target_kind == 'custom' or source_kind == 'custom':
        return False
    groups = [
        {'descricao', 'descricao_curta', 'descricao_complementar', 'nome_apoio'},
        {'codigo', 'id_produto', 'gtin'},
        {'preco_unitario', 'preco_custo'},
    ]
    if target_kind == source_kind:
        return True
    return any(target_kind in group and source_kind in group for group in groups)


def _semantic_conflict(target_kind: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> bool:
    content_kind = str(profile.get('content_kind') or profile.get('kind') or '')
    confidence = float(profile.get('confidence') or 0)
    if not content_kind or content_kind == 'custom' or confidence < 0.55:
        return False
    return not _is_kind_compatible(target_kind, content_kind)


def _auto_compatible(target: str, source: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> bool:
    target_key = normalize_column_key(target)
    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or '')
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    integer = float(profile.get('integer') or numeric)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)

    if target_kind == 'custom':
        return False
    if _semantic_conflict(target_kind, profile):
        return False
    if target_key in GENERIC_DESCRIPTION_TARGETS and not _is_kind_compatible(target_kind, source_kind):
        return False
    if target_kind in {'codigo', 'id_produto'}:
        return source_kind in {'codigo', 'id_produto', 'gtin'} or gtin >= 0.45 or numeric >= 0.70
    if target_kind == 'gtin':
        return source_kind == 'gtin' or gtin >= 0.55
    if target_kind in {'descricao', 'nome_apoio', 'descricao_curta', 'descricao_complementar'}:
        return _is_kind_compatible(target_kind, source_kind) or (text >= 0.55 and avg_len >= 8 and url < 0.20)
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return source_kind in {'preco_unitario', 'preco_custo'} or price >= 0.35 or (numeric >= 0.70 and integer < 0.75)
    if target_kind == 'estoque':
        if source_kind in {'preco_unitario', 'preco_custo'} or _source_has_price_name(str(profile.get('source_name') or '')):
            return False
        return source_kind == 'estoque' or (numeric >= 0.80 and price < 0.35)
    if target_kind == 'url':
        return source_kind == 'url' or url >= 0.60
    if target_kind == 'imagem':
        return source_kind == 'imagem' or image >= 0.35
    if target_kind == 'marca':
        return source_kind == 'marca' or (text >= 0.45 and avg_len <= 35 and url == 0)
    if target_kind == 'categoria':
        return source_kind == 'categoria' or (text >= 0.40 and avg_len <= 90)
    return source_kind == target_kind


def _content_bonus(target: str, source: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> int:
    profile = dict(profile)
    profile['source_name'] = source
    if not _auto_compatible(target, source, profile):
        return -1000
    target_kind = infer_kind(target)
    source_kind = str(profile.get('kind') or '')
    if _is_kind_compatible(target_kind, source_kind) and target_kind != 'custom':
        return 45
    if target_kind == 'gtin':
        return int(float(profile.get('gtin') or 0) * 45)
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(float(profile.get('price') or 0), float(profile.get('numeric') or 0)) * 35)
    if target_kind in {'descricao', 'nome_apoio', 'descricao_curta', 'descricao_complementar'}:
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
            bonus = _content_bonus(model_col, source_col, profiles[source_col])
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


# -----------------------------------------------------------------------------
# Confiança/farol do mapeamento.
# -----------------------------------------------------------------------------
def resolved_empty_confidence() -> dict[str, object]:
    return {'score': 100, 'level': 'verde', 'emoji': '🟢', 'label': 'vazio confirmado', 'order': 2, 'strict': True}


def pending_confidence() -> dict[str, object]:
    return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': 'precisa escolher', 'order': 0, 'strict': False}


def _target_kind(target: str) -> str:
    kind = infer_kind(target)
    if kind != 'custom':
        return kind
    target_key = normalize_column_key(target)
    for kind_name, aliases in FIELD_ALIASES.items():
        if any(normalize_column_key(alias) in target_key or target_key in normalize_column_key(alias) for alias in aliases):
            return kind_name
    return 'custom'


def _custom_equivalent(target: str, source: str) -> bool:
    target_key = normalize_column_key(target)
    source_key = normalize_column_key(source)
    target_compact = _compact_key(target)
    source_compact = _compact_key(source)

    if target_compact and source_compact and target_compact == source_compact:
        return True

    for aliases in CUSTOM_EQUIVALENT_TERMS.values():
        normalized_aliases = [normalize_column_key(alias) for alias in aliases]
        target_hit = target_key in normalized_aliases
        source_hit = source_key in normalized_aliases
        if target_hit and source_hit:
            return True
    return False


def _bit_to_bit_match(target: str, source: str) -> bool:
    return str(target) == str(source)


def _alias_score(target_kind: str, source: str) -> int:
    source_key = normalize_column_key(source)
    score = 0
    for alias in FIELD_ALIASES.get(target_kind, []):
        alias_key = normalize_column_key(alias)
        if alias_key and (alias_key in source_key or source_key in alias_key):
            score += 40
    return min(score, 80)


def _name_score(target: str, source: str) -> int:
    target_kind = _target_kind(target)
    target_key = normalize_column_key(target)
    source_key = normalize_column_key(source)
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


def _is_price_like_source(source: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> bool:
    source_key = normalize_column_key(source)
    if str(profile.get('kind') or '') in {'preco_unitario', 'preco_custo'}:
        return True
    return any(normalize_column_key(term) in source_key for term in PRICE_SOURCE_TERMS)


def _content_score(target: str, source: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> int:
    target_kind = _target_kind(target)
    source_kind = str(profile.get('kind') or infer_kind(source))
    has_values = bool(profile.get('has_values'))
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    integer = float(profile.get('integer') or numeric)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    avg_len = float(profile.get('avg_len') or 0)
    unique = float(profile.get('unique') or 0)

    if not has_values:
        return -80
    if _semantic_conflict(target_kind, profile):
        return -140
    if _is_kind_compatible(target_kind, source_kind) and target_kind != 'custom':
        return 70
    if target_kind in {'codigo', 'id_produto'}:
        return 45 if gtin >= 0.30 or numeric >= 0.55 or source_kind in {'codigo', 'id_produto', 'gtin'} else -80
    if target_kind == 'gtin':
        return int(gtin * 110) if gtin >= 0.50 or source_kind == 'gtin' else -120
    if target_kind in {'descricao', 'nome_apoio', 'descricao_curta', 'descricao_complementar'}:
        return int(text * 55 + min(avg_len, 80) / 3) if text >= 0.40 and url < 0.25 else -80
    if target_kind in {'preco_unitario', 'preco_custo'}:
        return int(max(price, numeric) * 90) if price >= 0.25 or (numeric >= 0.70 and integer < 0.75) else -90
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


def _confidence_compatible(target: str, source: str, profile: dict[str, float | str | bool | tuple[str, ...]]) -> bool:
    target_kind = _target_kind(target)
    if _semantic_conflict(target_kind, profile):
        return False
    return _content_score(target, source, profile) > -70 or _name_score(target, source) >= 100


def _confidence(score: int, level_hint: str = '') -> dict[str, object]:
    if level_hint == 'verde':
        return {'score': 100, 'level': 'verde', 'emoji': '🟢', 'label': '100% bit a bit', 'order': 2, 'strict': True}

    raw_score = int(score)
    safe_score = min(max(raw_score, 0), 99)
    if raw_score >= 130:
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
    target_kind = _target_kind(target)
    if _semantic_conflict(target_kind, profile):
        warning = str(profile.get('warning') or 'Cabeçalho e conteúdo não combinam com o campo final.')
        return {'score': 0, 'level': 'vermelho', 'emoji': '🔴', 'label': warning, 'order': 0, 'strict': True}
    if not _confidence_compatible(target, source, profile):
        return pending_confidence()

    if _bit_to_bit_match(target, source) and not bool(profile.get('header_conflict')):
        return _confidence(100, 'verde')

    score = _name_score(target, source) + _content_score(target, source, profile)
    result = _confidence(score)
    if result.get('level') == 'verde' and bool(profile.get('header_conflict')):
        result = dict(result)
        result['level'] = 'amarelo'
        result['emoji'] = '🟡'
        result['label'] = 'conferir: cabeçalho e conteúdo divergem'
        result['order'] = 1
    return result


def confidence_for_mapping_dict(df_source: pd.DataFrame, mapping: dict[str, str]) -> dict[str, dict[str, object]]:
    return {target: confidence_for_mapping(df_source, target, source) for target, source in dict(mapping or {}).items()}


def sort_targets_by_confidence(target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    def key(target: str) -> tuple[int, int, str]:
        info = confidence.get(target, {}) if isinstance(confidence, dict) else {}
        return (int(info.get('order', 0) or 0), int(info.get('score', 0) or 0), normalize_column_key(target))

    return sorted([str(column) for column in target_columns], key=key)


# -----------------------------------------------------------------------------
# Estado da tela de mapeamento manual/assistido.
# -----------------------------------------------------------------------------
def confidence_for(target: str, source_column: str, source: Any = None) -> tuple[str, str]:
    if not source_column:
        return CONFIDENCE_EMPTY, '🔴 vazio'

    if isinstance(source, pd.DataFrame) and source_column in source.columns:
        info = confidence_for_mapping(source, target, source_column)
        level = str(info.get('level') or '')
        emoji = str(info.get('emoji') or '')
        label = str(info.get('label') or '')
        score = info.get('score', '')
        suffix = f' {score}%' if isinstance(score, int) and score > 0 else ''
        if level == 'verde':
            return CONFIDENCE_HIGH, f'{emoji} {label}{suffix}'.strip()
        if level == 'amarelo':
            return CONFIDENCE_REVIEW, f'{emoji} {label}{suffix}'.strip()
        return CONFIDENCE_EMPTY, f'{emoji or "🔴"} {label or "revisar conteúdo"}'.strip()

    target_key = normalize_engine_key(target)
    source_key = normalize_engine_key(source_column)
    if target_key and (target_key == source_key or target_key in source_key or source_key in target_key):
        return CONFIDENCE_HIGH, '🟢 alto'
    if source is not None and source_has_values(source, source_column):
        return CONFIDENCE_REVIEW, '🟡 revisar'
    return CONFIDENCE_EMPTY, '🔴 vazio'


def normalize_selected_source(value: object) -> str:
    text = str(value or '').strip()
    return '' if text == EMPTY_OPTION else text


def build_mapping_state(
    request: MappingRequest,
    mapping: Mapping[str, str] | None = None,
    *,
    source: Any = None,
    engine: str = 'local',
    message: str = '',
) -> MappingCommandResult:
    current = {str(k): normalize_selected_source(v) for k, v in dict(mapping or {}).items()}
    fields: list[MappingField] = []
    rows: list[dict[str, str]] = []
    for target in request.target_columns:
        target_name = str(target)
        selected = current.get(target_name, '')
        confidence, label = confidence_for(target_name, selected, source)
        field = MappingField(target=target_name, source=selected, confidence=confidence, label=label)
        fields.append(field)
        row = {'Farol': label, 'Contrato final': target_name, 'Origem usada': selected or '(vazio)'}
        if selected and isinstance(source, pd.DataFrame) and selected in source.columns:
            profile = _profile(source, selected)
            leitura = str(profile.get('kind') or profile.get('content_kind') or '')
            if leitura:
                row['Leitura IA'] = leitura
            warning = str(profile.get('warning') or '')
            if warning:
                row['Alerta IA'] = warning
        rows.append(row)
    state = MappingState(request=request, fields=tuple(fields), engine=engine or 'local', message=message)
    return MappingCommandResult(state=state, rows=tuple(rows), message=message, needs_rerun=False)


def mapping_options(source_columns: tuple[str, ...] | list[str]) -> list[str]:
    return [EMPTY_OPTION] + [str(column) for column in list(source_columns or [])]


def _safe_frame_columns(frame: Any) -> tuple[str, ...]:
    """Extrai colunas sem avaliar pandas.Index como booleano.

    O fluxo universal recebe DataFrames e também pode receber estruturas vazias
    em recuperação de estado. Nunca use ``frame.columns or []`` aqui, porque
    ``pandas.Index`` não tem valor booleano definido e quebra com:
    ``ValueError: The truth value of a Index is ambiguous``.
    """
    columns = getattr(frame, 'columns', None)
    if columns is None:
        if isinstance(frame, dict):
            columns = frame.keys()
        elif isinstance(frame, (list, tuple, set)):
            columns = frame
        else:
            return tuple()

    try:
        return tuple(str(col) for col in list(columns))
    except Exception:
        return tuple()


def simulate_universal_mapping_request() -> dict[str, object]:
    """Simulação leve do fluxo universal para diagnóstico BLINGSCAN/BLINGFIX.

    A simulação cria DataFrames de origem/modelo com ``pandas.Index`` real,
    passa pelo mesmo construtor de request usado no mapeamento e confirma que
    nenhuma etapa depende de ``columns or []`` e que conteúdo conflitante não
    passa como sugestão verde.
    """
    source = pd.DataFrame(
        {
            'SKU': ['ABC-1'],
            'Produto': ['7891234567890'],
            'Título real': ['Produto teste bluetooth'],
            'Preço': ['R$ 10,00'],
            'Estoque': ['5'],
        }
    )
    model = pd.DataFrame(columns=['Código', 'Descrição', 'GTIN', 'Preço unitário', 'Estoque'])
    request = build_request_from_frames(source, model, operation='universal', signature='simulation')
    mapping = auto_map_columns(source, model)
    result = build_mapping_state(
        request,
        mapping,
        source=source,
        engine='local_simulation',
        message='Simulação do fluxo universal corrigido.',
    )
    output = apply_mapping(source, model, result.state.mapping)
    return {
        'operation': request.operation,
        'source_columns': list(request.source_columns),
        'target_columns': list(request.target_columns),
        'mapping': result.state.mapping,
        'rows_report': list(result.rows),
        'mapped_fields': sum(1 for value in result.state.mapping.values() if str(value or '').strip()),
        'descricao_from_produto_blocked': result.state.mapping.get('Descrição') != 'Produto',
        'gtin_from_produto_detected': result.state.mapping.get('GTIN') == 'Produto',
        'rows': int(len(output)),
        'columns': int(len(output.columns)),
        'ok': bool(request.source_columns and request.target_columns and len(output) == len(source)),
    }


def build_request_from_frames(source: Any, target: Any, *, operation: str = 'universal', signature: str = '') -> MappingRequest:
    source_columns = _safe_frame_columns(source)
    target_columns = _safe_frame_columns(target)
    return MappingRequest(operation=operation, signature=signature, source_columns=source_columns, target_columns=target_columns)


def build_full_mapping_result(
    df_source: pd.DataFrame,
    df_model: pd.DataFrame,
    *,
    operation: str = 'universal',
    signature: str = '',
    engine: str = 'local',
) -> MappingCommandResult:
    """Entrada única para anexos: sugere, calcula confiança e monta estado da UI."""
    mapping = auto_map_columns(df_source, df_model)
    request = build_request_from_frames(df_source, df_model, operation=operation, signature=signature)
    return build_mapping_state(request, mapping, source=df_source, engine=engine, message='Mapeamento centralizado gerado por planilha anexada.')


__all__ = [
    'FIELD_ALIASES',
    'MappingCommandResult',
    'SYNONYMS',
    'apply_mapping',
    'auto_map_columns',
    'build_full_mapping_result',
    'build_mapping_state',
    'build_model_from_columns',
    'build_request_from_frames',
    'confidence_for',
    'confidence_for_mapping',
    'confidence_for_mapping_dict',
    'mapping_options',
    'normalize_engine_key',
    'normalize_key',
    'normalize_selected_source',
    'pending_confidence',
    'resolved_empty_confidence',
    'simulate_universal_mapping_request',
    'sort_targets_by_confidence',
    'source_has_values',
]