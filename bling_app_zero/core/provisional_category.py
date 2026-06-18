from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from bling_app_zero.core.user_rules import get_user_rules

RESPONSIBLE_FILE = 'bling_app_zero/core/provisional_category.py'

DEFAULT_PROVISIONAL_CATEGORY = 'Produtos não classificados'
DEFAULT_CATEGORY_CONFIDENCE_MIN = 0.80

CATEGORY_FIELD_CANDIDATES = (
    'Categoria',
    'categoria',
    'Categoria do produto',
    'Categoria Produto',
    'Nome da categoria',
    'category',
    'categoria_sugerida_ia',
    'categoria_atual_ia',
)

PRODUCT_NAME_CANDIDATES = (
    'Descrição',
    'Descricao',
    'Nome',
    'Nome do produto',
    'Produto',
    'Título',
    'Titulo',
    'name',
    'nome',
)

PRODUCT_DESCRIPTION_CANDIDATES = (
    'Descrição Curta',
    'Descricao Curta',
    'Descrição complementar',
    'Descricao complementar',
    'Características',
    'Caracteristicas',
    'Ficha técnica',
    'Ficha tecnica',
    'description',
    'descricao',
)

GENERIC_OR_BLOCKED_CATEGORIES = {
    '',
    'home',
    'inicio',
    'início',
    'loja',
    'produto',
    'produtos',
    'catalogo',
    'catálogo',
    'departamento',
    'departamentos',
    'categoria',
    'categorias',
    'todos',
    'ofertas',
    'promocoes',
    'promoções',
    'mais vendidos',
    'novidades',
    'mega center',
    'stoqui',
    'informatica',
    'informática',
    'alimentos',
    'revisar manualmente',
    'revisar',
    'produtos nao classificados',
    'produtos não classificados',
    'nao classificados',
    'não classificados',
    'sem classificacao',
    'sem classificação',
}


@dataclass(frozen=True)
class CategoryGuardResult:
    payload: dict[str, Any]
    applied: bool
    provisional: bool
    category_name: str
    category_id: str
    source: str
    reason: str
    rule_enabled: bool
    confidence: float = 0.0


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _clean_category(value: object, *, limit: int = 80) -> str:
    text = str(value or '').replace('\ufeff', '').replace('\u200b', '').strip()
    text = re.sub(r'\s+', ' ', text).strip(' -|/\\;:,.')
    if not text:
        return ''
    parts = [part.strip(' -|/\\;:,.') for part in re.split(r'\s*(?:>|/|\\|\||;|»|›)\s*', text) if part.strip()]
    candidate = parts[-1] if parts else text
    return candidate[:limit].strip()


def _is_blocked_category(value: object) -> bool:
    normalized = _norm(_clean_category(value))
    return not normalized or normalized in {_norm(item) for item in GENERIC_OR_BLOCKED_CATEGORIES}


def _usable_category(value: object) -> str:
    category = _clean_category(value)
    if _is_blocked_category(category):
        return ''
    normalized = _norm(category)
    if len(normalized) < 3:
        return ''
    if re.fullmatch(r'[0-9._/-]+', normalized):
        return ''
    return category


def _payload_has_category(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    category = payload.get('categoria')
    values: list[str] = []
    if isinstance(category, dict):
        values = [str(value or '').strip() for value in category.values()]
    elif str(category or '').strip():
        values = [str(category or '').strip()]
    return any(value and not _is_blocked_category(value) for value in values)


def _row_value(row: Any, key: str) -> str:
    try:
        value = row.get(key, '')
    except Exception:
        return ''
    return '' if value is None else str(value).strip()


def _first_row_value(row: Any, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _row_value(row, key)
        if value:
            return value
    return ''


def category_from_row(row: Any, meta: dict[str, Any] | None = None) -> tuple[str, str]:
    meta_category = _usable_category((meta or {}).get('category'))
    if meta_category:
        return meta_category, 'payload_meta_category'
    for key in CATEGORY_FIELD_CANDIDATES:
        value = _usable_category(_row_value(row, key))
        if value:
            return value, key
    return '', ''


def _category_confidence_min() -> float:
    try:
        rules = get_user_rules()
    except Exception:
        rules = {}
    raw = rules.get('category_ai_confidence_min', DEFAULT_CATEGORY_CONFIDENCE_MIN)
    try:
        value = float(raw)
    except Exception:
        value = DEFAULT_CATEGORY_CONFIDENCE_MIN
    if value > 1:
        value = value / 100
    return min(0.99, max(0.50, value))


def category_from_intelligence(row: Any, payload: dict[str, Any] | None = None, meta: dict[str, Any] | None = None) -> tuple[str, str, float, str]:
    """Classifica categoria real por contexto do produto antes da categoria provisória.

    Usa a inteligência determinística de categoria já usada na etapa de categorização.
    Não substitui categoria captada; só atua quando ela veio vazia/genérica.
    """
    try:
        from bling_app_zero.core.category_intelligence import suggest_category_for_product
    except Exception:
        return '', '', 0.0, 'category_intelligence_unavailable'

    payload = payload or {}
    meta = meta or {}
    name = str(payload.get('nome') or '').strip() or _first_row_value(row, PRODUCT_NAME_CANDIDATES)
    description = str(payload.get('descricaoCurta') or '').strip() or _first_row_value(row, PRODUCT_DESCRIPTION_CANDIDATES)
    current_category = str(meta.get('category') or '').strip() or _first_row_value(row, CATEGORY_FIELD_CANDIDATES)
    if not name and not description:
        return '', '', 0.0, 'sem_nome_ou_descricao_para_classificar'

    try:
        suggestion = suggest_category_for_product(name, description=description, current_category=current_category)
    except Exception as exc:
        return '', '', 0.0, f'category_intelligence_exception:{str(exc)[:120]}'

    category = _usable_category(getattr(suggestion, 'category', ''))
    confidence = float(getattr(suggestion, 'confidence', 0.0) or 0.0)
    reason = str(getattr(suggestion, 'reason', '') or 'categoria por inteligência')
    if not category:
        return '', '', confidence, reason or 'categoria_nao_confiavel'
    if confidence < _category_confidence_min():
        return '', '', confidence, f'confianca_baixa:{reason}'
    return category, 'category_intelligence', confidence, reason


def provisional_category_from_rules() -> tuple[bool, str]:
    try:
        rules = get_user_rules()
    except Exception:
        rules = {}
    enabled = bool(rules.get('allow_provisional_category', True))
    category_name = _clean_category(rules.get('provisional_category_name')) or DEFAULT_PROVISIONAL_CATEGORY
    if _is_blocked_category(category_name) and _norm(category_name) != _norm(DEFAULT_PROVISIONAL_CATEGORY):
        category_name = DEFAULT_PROVISIONAL_CATEGORY
    return enabled, category_name


def apply_category_guard_to_payload(
    payload: dict[str, Any],
    *,
    row: Any | None = None,
    meta: dict[str, Any] | None = None,
    category_id_resolver: Callable[[str], str] | None = None,
) -> CategoryGuardResult:
    """Garante categoria no payload sem inventar categoria real.

    Ordem segura:
    1. Se o payload já tem categoria real, não altera.
    2. Se a categoria atual for provisória/genérica, ignora e tenta substituir.
    3. Recupera categoria real de meta/linha, inclusive colunas auxiliares da IA.
    4. Tenta classificar categoria real pelo contexto do produto com confiança mínima.
    5. Se ainda não existir, aplica categoria provisória universal.
    6. Só bloqueia se a regra provisória for desligada manualmente.
    """
    current = dict(payload or {})
    rule_enabled, provisional_name = provisional_category_from_rules()

    if _payload_has_category(current):
        return CategoryGuardResult(current, False, False, '', '', 'payload', 'payload_already_has_real_category', rule_enabled, 1.0)

    real_category, real_source = category_from_row(row, meta)
    confidence = 1.0 if real_category else 0.0
    reason = 'real_category_recovered' if real_category else ''
    if not real_category:
        real_category, real_source, confidence, reason = category_from_intelligence(row, current, meta)

    category_name = real_category or (provisional_name if rule_enabled else '')
    if not category_name:
        return CategoryGuardResult(current, False, False, '', '', '', 'missing_category_and_provisional_disabled', rule_enabled, confidence)

    category_id = ''
    if category_id_resolver is not None:
        try:
            category_id = str(category_id_resolver(category_name) or '').strip()
        except Exception:
            category_id = ''

    if category_id:
        current['categoria'] = {'id': category_id}
    else:
        current['categoria'] = {'descricao': category_name}

    provisional = not bool(real_category)
    return CategoryGuardResult(
        current,
        True,
        provisional,
        category_name,
        category_id,
        real_source if real_category else 'provisional_rule',
        reason if real_category else 'provisional_category_applied',
        rule_enabled,
        confidence,
    )


__all__ = [
    'CategoryGuardResult',
    'DEFAULT_PROVISIONAL_CATEGORY',
    'RESPONSIBLE_FILE',
    'apply_category_guard_to_payload',
    'category_from_intelligence',
    'category_from_row',
    'provisional_category_from_rules',
]
