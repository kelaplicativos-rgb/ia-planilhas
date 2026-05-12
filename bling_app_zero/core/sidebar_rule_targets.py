from __future__ import annotations

from typing import Iterable

from bling_app_zero.core.gtin import looks_like_gtin_column
from bling_app_zero.core.post_mapping_defaults import COLUMN_DEFAULT_KEY_BY_TARGET
from bling_app_zero.core.text import normalize_key
from bling_app_zero.core.user_rules import get_user_rules

SIDEBAR_RULE_DOT = '🟣'
SIDEBAR_RULE_LABEL = 'regra/recurso do sidebar'

INTERNAL_DEFAULT_TARGETS = {
    'unidade',
    'altura',
    'largura',
    'profundidade',
    'comprimento',
    'itens por caixa',
    'itens p/ caixa',
}

IMAGE_TARGET_TERMS = {
    'imagem',
    'imagens',
    'image',
    'images',
    'foto',
    'fotos',
    'url imagem',
    'url imagens',
    'url imagens externas',
}

CODE_TARGET_KEYS = {
    'codigo',
    'código',
    'codigo produto',
    'código produto',
    'codigo do produto',
    'código do produto',
    'sku',
    'referencia',
    'referência',
    'cod fornecedor',
    'cód fornecedor',
    'cod no fornecedor',
    'cód no fornecedor',
    'codigo no fornecedor',
    'código no fornecedor',
}

MEASURE_TARGET_TERMS = {
    'altura',
    'largura',
    'profundidade',
    'comprimento',
}

MEASURE_NEGATIVE_TERMS = {
    'peso',
    'preco',
    'preço',
    'valor',
    'estoque',
    'saldo',
    'quantidade',
    'gtin',
    'ean',
    'sku',
    'codigo',
    'código',
}


def _rules() -> dict:
    try:
        return get_user_rules()
    except Exception:
        return {}


def _looks_like_image_target(target: object) -> bool:
    key = normalize_key(target)
    return any(normalize_key(term) in key for term in IMAGE_TARGET_TERMS)


def _looks_like_code_target(target: object) -> bool:
    key = normalize_key(target)
    if not key or looks_like_gtin_column(target):
        return False
    return key in {normalize_key(term) for term in CODE_TARGET_KEYS}


def _looks_like_measure_target(target: object) -> bool:
    key = normalize_key(target)
    if not key:
        return False
    if any(term in key for term in MEASURE_NEGATIVE_TERMS):
        return False
    return any(term in key for term in MEASURE_TARGET_TERMS)


def sidebar_rule_target_keys(target_columns: Iterable[object]) -> set[str]:
    rules = _rules()
    targets: set[str] = set()
    post_mapping_targets = set(COLUMN_DEFAULT_KEY_BY_TARGET.keys())

    for target in target_columns:
        key = normalize_key(target)
        if not key:
            continue
        if key in post_mapping_targets or key in INTERNAL_DEFAULT_TARGETS:
            targets.add(key)
        if bool(rules.get('clean_invalid_gtin', True)) and looks_like_gtin_column(target):
            targets.add(key)
        if bool(rules.get('normalize_image_separator', True)) and _looks_like_image_target(target):
            targets.add(key)
        if bool(rules.get('normalize_measures_to_meters', True)) and _looks_like_measure_target(target):
            targets.add(key)
        if (bool(rules.get('auto_product_code', True)) or bool(rules.get('unique_product_code', True))) and _looks_like_code_target(target):
            targets.add(key)

    custom_rules = rules.get('custom_rules', [])
    if isinstance(custom_rules, list):
        for rule in custom_rules:
            if not isinstance(rule, dict) or not bool(rule.get('enabled', False)):
                continue
            target = str(rule.get('target_column') or rule.get('condition') or '').strip()
            if target:
                targets.add(normalize_key(target))

    return targets


def has_sidebar_rule(target: object, target_keys: set[str] | None = None) -> bool:
    key = normalize_key(target)
    if target_keys is None:
        return key in sidebar_rule_target_keys([target])
    return key in target_keys


def append_sidebar_rule_dot(label: str, target_keys: set[str] | None = None) -> str:
    text = str(label or '').strip()
    if SIDEBAR_RULE_DOT in text:
        return text
    target = text
    for prefix in ('🔴', '🟡', '🟢'):
        if target.startswith(prefix):
            target = target[len(prefix):].strip()
            break
    if has_sidebar_rule(target, target_keys):
        if text.startswith(('🔴', '🟡', '🟢')):
            return f'{text[:1]} {SIDEBAR_RULE_DOT} {text[1:].strip()}'
        return f'{SIDEBAR_RULE_DOT} {text}'
    return text


__all__ = [
    'SIDEBAR_RULE_DOT',
    'SIDEBAR_RULE_LABEL',
    'append_sidebar_rule_dot',
    'has_sidebar_rule',
    'sidebar_rule_target_keys',
]
