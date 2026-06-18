from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from bling_app_zero.core.user_rules import get_user_rules

RESPONSIBLE_FILE = 'bling_app_zero/core/provisional_category.py'

DEFAULT_PROVISIONAL_CATEGORY = 'Produtos não classificados'

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


def _usable_category(value: object) -> str:
    category = _clean_category(value)
    normalized = _norm(category)
    if not normalized or normalized in {_norm(item) for item in GENERIC_OR_BLOCKED_CATEGORIES}:
        return ''
    if len(normalized) < 3:
        return ''
    if re.fullmatch(r'[0-9._/-]+', normalized):
        return ''
    return category


def _payload_has_category(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    category = payload.get('categoria')
    if isinstance(category, dict):
        return any(str(value or '').strip() for value in category.values())
    return bool(str(category or '').strip())


def _row_value(row: Any, key: str) -> str:
    try:
        value = row.get(key, '')
    except Exception:
        return ''
    return '' if value is None else str(value).strip()


def category_from_row(row: Any, meta: dict[str, Any] | None = None) -> tuple[str, str]:
    meta_category = _usable_category((meta or {}).get('category'))
    if meta_category:
        return meta_category, 'payload_meta_category'
    for key in CATEGORY_FIELD_CANDIDATES:
        value = _usable_category(_row_value(row, key))
        if value:
            return value, key
    return '', ''


def provisional_category_from_rules() -> tuple[bool, str]:
    try:
        rules = get_user_rules()
    except Exception:
        rules = {}
    enabled = bool(rules.get('allow_provisional_category', True))
    category_name = _usable_category(rules.get('provisional_category_name')) or DEFAULT_PROVISIONAL_CATEGORY
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
    1. Se o payload já tem categoria, não altera.
    2. Recupera categoria real de meta/linha, inclusive colunas auxiliares da IA.
    3. Se ainda não existir, aplica categoria provisória universal.
    4. Só bloqueia se a regra provisória for desligada manualmente.
    """
    current = dict(payload or {})
    rule_enabled, provisional_name = provisional_category_from_rules()

    if _payload_has_category(current):
        return CategoryGuardResult(current, False, False, '', '', 'payload', 'payload_already_has_category', rule_enabled)

    real_category, real_source = category_from_row(row, meta)
    category_name = real_category or (provisional_name if rule_enabled else '')
    if not category_name:
        return CategoryGuardResult(current, False, False, '', '', '', 'missing_category_and_provisional_disabled', rule_enabled)

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
        'real_category_recovered' if real_category else 'provisional_category_applied',
        rule_enabled,
    )


__all__ = [
    'CategoryGuardResult',
    'DEFAULT_PROVISIONAL_CATEGORY',
    'RESPONSIBLE_FILE',
    'apply_category_guard_to_payload',
    'category_from_row',
    'provisional_category_from_rules',
]
