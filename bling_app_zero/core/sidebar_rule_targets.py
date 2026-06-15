from __future__ import annotations

from typing import Iterable

from bling_app_zero.core.gtin import looks_like_gtin_column
from bling_app_zero.core.post_mapping_defaults import COLUMN_DEFAULT_KEY_BY_TARGET, get_post_mapping_defaults_config
from bling_app_zero.core.text import normalize_key
from bling_app_zero.core.user_rules import get_user_rules

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

SIDEBAR_RULE_DOT = '🟣'
SIDEBAR_RULE_LABEL = 'preenchido por regra/recurso'

# Mesmo nome usado na Central de Regras do fluxo principal.
# A sidebar não controla mais regra; este estado nasce e muda somente no meio do fluxo.
DEFAULT_RULES_ENABLED_KEY = 'rules_center_default_rules_enabled'

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


def _clean_target_label(target: object) -> str:
    text = str(target or '').strip()
    for prefix in ('🔴', '🟡', '🟢', SIDEBAR_RULE_DOT):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    for separator in ('·', '|'):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
    return text


def _looks_like_image_target(target: object) -> bool:
    key = normalize_key(_clean_target_label(target))
    return any(normalize_key(term) in key for term in IMAGE_TARGET_TERMS)


def _looks_like_code_target(target: object) -> bool:
    clean_target = _clean_target_label(target)
    key = normalize_key(clean_target)
    if not key or looks_like_gtin_column(clean_target):
        return False
    return key in {normalize_key(term) for term in CODE_TARGET_KEYS}


def _looks_like_measure_target(target: object) -> bool:
    key = normalize_key(_clean_target_label(target))
    if not key:
        return False
    if any(term in key for term in MEASURE_NEGATIVE_TERMS):
        return False
    return any(term in key for term in MEASURE_TARGET_TERMS)


def _optional_defaults_enabled() -> bool:
    if st is None:
        return False
    return bool(st.session_state.get(DEFAULT_RULES_ENABLED_KEY, False))


def _post_mapping_defaults_enabled() -> bool:
    if not _optional_defaults_enabled():
        return False
    try:
        config = get_post_mapping_defaults_config()
    except Exception:
        return False
    return bool(config.get('enabled', False))


def _enabled_custom_rule_targets(rules: dict) -> set[str]:
    targets: set[str] = set()
    custom_rules = rules.get('custom_rules', [])
    if not isinstance(custom_rules, list):
        return targets
    for rule in custom_rules:
        if not isinstance(rule, dict) or not bool(rule.get('enabled', False)):
            continue
        target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if target:
            targets.add(normalize_key(target))
    return targets


def sidebar_rule_target_keys(target_columns: Iterable[object]) -> set[str]:
    """Campos que devem receber indicador roxo no mapeamento.

    Regra do BLINGFIX:
    - Regras e padrões só existem no fluxo principal, não na sidebar.
    - Padrões opcionais desligados não podem pintar campo de roxo.
    - Proteções do CSV final continuam independentes: GTIN, imagens, limite de imagens e código.
    """
    rules = _rules()
    targets: set[str] = set()
    optional_defaults_enabled = _optional_defaults_enabled()
    enabled_custom_targets = _enabled_custom_rule_targets(rules) if optional_defaults_enabled else set()
    post_mapping_targets = set(COLUMN_DEFAULT_KEY_BY_TARGET.keys()) if _post_mapping_defaults_enabled() else set()

    image_rule_enabled = bool(rules.get('normalize_image_separator', True)) or bool(rules.get('limit_bling_images', True))

    for target in target_columns:
        clean_target = _clean_target_label(target)
        key = normalize_key(clean_target)
        if not key:
            continue

        if optional_defaults_enabled and (key in enabled_custom_targets or key in INTERNAL_DEFAULT_TARGETS):
            targets.add(key)

        if key in post_mapping_targets:
            targets.add(key)

        if bool(rules.get('clean_invalid_gtin', True)) and looks_like_gtin_column(clean_target):
            targets.add(key)
        if image_rule_enabled and _looks_like_image_target(clean_target):
            targets.add(key)
        if bool(rules.get('normalize_measures_to_meters', False)) and _looks_like_measure_target(clean_target):
            targets.add(key)
        if (bool(rules.get('auto_product_code', True)) or bool(rules.get('unique_product_code', True))) and _looks_like_code_target(clean_target):
            targets.add(key)

    return targets


def has_sidebar_rule(target: object, target_keys: set[str] | None = None) -> bool:
    key = normalize_key(_clean_target_label(target))
    if target_keys is None:
        return key in sidebar_rule_target_keys([target])
    return key in target_keys


def append_sidebar_rule_dot(label: str, target_keys: set[str] | None = None) -> str:
    """Troca o farol principal por lilás quando o campo é resolvido por regra/recurso."""
    text = str(label or '').strip()
    clean_target = _clean_target_label(text)

    if not has_sidebar_rule(clean_target, target_keys):
        return text

    suffix = ''
    if '·' in text:
        suffix = ' · ' + text.split('·', 1)[1].strip()

    return f'{SIDEBAR_RULE_DOT} {clean_target}{suffix}'


__all__ = [
    'SIDEBAR_RULE_DOT',
    'SIDEBAR_RULE_LABEL',
    'append_sidebar_rule_dot',
    'has_sidebar_rule',
    'sidebar_rule_target_keys',
]
