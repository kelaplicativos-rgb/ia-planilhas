from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules

RULES_CENTER_READY_KEY = 'rules_center_reviewed'

PROTECTION_FIELDS = [
    ('clean_invalid_gtin', 'Limpar GTIN inválido', 'GTIN fora do padrão sai vazio no arquivo final.'),
    ('normalize_image_separator', 'Separar imagens por |', 'Múltiplas imagens saem como img1|img2|img3.'),
    ('normalize_measures_to_meters', 'Normalizar medidas', 'Padroniza altura, largura, profundidade e comprimento no formato esperado.'),
    ('auto_product_code', 'Gerar código quando vazio', 'Preenche código/SKU somente quando o campo estiver vazio.'),
    ('unique_product_code', 'Evitar código duplicado', 'Ajusta códigos repetidos quando o recurso estiver ativo.'),
]

DEFAULT_FIELDS = [
    ('Unidade', 'measure_unit_default', 'UN'),
    ('Altura', 'height_default', '2'),
    ('Largura', 'width_default', '11'),
    ('Profundidade', 'depth_default', '18'),
    ('Comprimento', 'length_default', '18'),
    ('Itens por caixa', 'box_items_default', '1'),
]

EXTRA_DEFAULT_RULES = [
    ('Categoria', ''),
    ('Clonar dados do pai', 'Não'),
    ('Condição do produto', 'Novo'),
    ('Descrição Complementar', ''),
    ('Frete Grátis', 'Não'),
    ('Informações Adicionais', ''),
    ('Situação', 'Ativo'),
    ('Unidade de medida', 'Centímetro'),
    ('Vídeo', ''),
    ('Volumes', '1'),
]


def _rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def _custom_rules_by_column(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rule in rules.get('custom_rules', []) or []:
        if not isinstance(rule, dict):
            continue
        target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if target:
            out[target.lower()] = dict(rule)
    return out


def _upsert_system_rule(custom_rules: list[dict[str, Any]], target_column: str, fill_value: str, enabled: bool) -> list[dict[str, Any]]:
    target_key = target_column.strip().lower()
    updated: list[dict[str, Any]] = []
    found = False
    for rule in custom_rules:
        if not isinstance(rule, dict):
            continue
        current_target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if current_target.lower() == target_key:
            current = dict(rule)
            current['id'] = str(current.get('id') or _rule_id(target_column))
            current['condition'] = target_column
            current['target_column'] = target_column
            current['fill_value'] = str(fill_value or '')
            current['only_when_empty'] = True
            current['enabled'] = bool(enabled)
            current['source'] = 'system'
            updated.append(current)
            found = True
        else:
            updated.append(dict(rule))
    if not found:
        updated.append(
            {
                'id': _rule_id(target_column),
                'condition': target_column,
                'target_column': target_column,
                'fill_value': str(fill_value or ''),
                'only_when_empty': True,
                'enabled': bool(enabled),
                'source': 'system',
            }
        )
    return updated


def _render_protection_rules(rules: dict[str, Any]) -> dict[str, Any]:
    st.markdown('#### Proteções do CSV final')
    st.caption('Nada aqui usa IA. São recursos objetivos de limpeza e segurança do arquivo final.')
    updated = dict(rules)
    for key, label, help_text in PROTECTION_FIELDS:
        updated[key] = st.toggle(label, value=bool(updated.get(key, False)), help=help_text, key=f'rules_center_{key}')
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    return updated


def _render_default_rules(rules: dict[str, Any]) -> dict[str, Any]:
    st.markdown('#### Padrões internos')
    st.caption('Esses valores só entram quando a coluna existir e a célula estiver vazia depois do mapeamento manual.')
    updated = dict(rules)
    custom_rules = list(updated.get('custom_rules', []) or [])
    custom_by_column = _custom_rules_by_column(updated)

    for label, key, fallback in DEFAULT_FIELDS:
        current_value = str(updated.get(key) or fallback)
        rule = custom_by_column.get(label.lower(), {})
        col_enabled, col_value = st.columns([0.34, 0.66])
        with col_enabled:
            enabled = st.toggle(f'Usar {label}', value=bool(rule.get('enabled', False)), key=f'rules_center_default_enabled_{key}')
        with col_value:
            value = st.text_input(label, value=current_value, key=f'rules_center_default_value_{key}')
        updated[key] = value
        custom_rules = _upsert_system_rule(custom_rules, label, value, enabled)

    st.markdown('#### Padrões finais opcionais')
    for target, fallback in EXTRA_DEFAULT_RULES:
        custom_by_column = _custom_rules_by_column({'custom_rules': custom_rules})
        rule = custom_by_column.get(target.lower(), {})
        col_enabled, col_value = st.columns([0.34, 0.66])
        with col_enabled:
            enabled = st.toggle(f'Usar {target}', value=bool(rule.get('enabled', False)), key=f'rules_center_extra_enabled_{_rule_id(target)}')
        with col_value:
            value = st.text_input(target, value=str(rule.get('fill_value') if rule else fallback), key=f'rules_center_extra_value_{_rule_id(target)}')
        custom_rules = _upsert_system_rule(custom_rules, target, value, enabled)

    updated['custom_rules'] = custom_rules
    return updated


def render_rules_center_step() -> None:
    st.markdown('### Regras e Padrões')
    st.caption('Central visível do fluxo. Regras importantes não ficam mais escondidas na sidebar.')
    st.info('Regra principal: mapeamento/manual ganha. Padrões só completam células vazias depois do mapeamento.')

    rules = get_user_rules()
    rules = _render_protection_rules(rules)
    st.divider()
    rules = _render_default_rules(rules)

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar regras desta sessão', use_container_width=True, key='rules_center_save'):
            set_user_rules(rules)
            st.session_state[RULES_CENTER_READY_KEY] = True
            st.success('Regras e padrões salvos para esta sessão.')
            st.rerun()
    with col_reset:
        if st.button('Restaurar padrões', use_container_width=True, key='rules_center_reset'):
            reset_user_rules()
            st.session_state[RULES_CENTER_READY_KEY] = True
            st.success('Padrões restaurados.')
            st.rerun()

    if st.button('Confirmar e continuar', use_container_width=True, key='rules_center_confirm'):
        set_user_rules(rules)
        st.session_state[RULES_CENTER_READY_KEY] = True
        st.success('Central de regras confirmada.')
        st.rerun()


def rules_center_ready() -> bool:
    return bool(st.session_state.get(RULES_CENTER_READY_KEY, False))


__all__ = ['RULES_CENTER_READY_KEY', 'render_rules_center_step', 'rules_center_ready']
