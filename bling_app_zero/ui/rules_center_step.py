from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules
from bling_app_zero.ui.home_wizard_constants import STEP_ENTRADA, STEP_REGRAS, WIZARD_STEP_KEY

RULES_CENTER_READY_KEY = 'rules_center_reviewed'
RULES_CENTER_ADVANCED_KEY = 'rules_center_advanced_to_next_step'

PROTECTION_FIELDS = [
    ('clean_invalid_gtin', 'GTIN inválido', 'GTIN fora do padrão sai vazio no arquivo final.'),
    ('normalize_image_separator', 'Imagens por |', 'Múltiplas imagens saem como img1|img2|img3.'),
    ('auto_product_code', 'Código automático', 'Preenche código/SKU somente quando o campo estiver vazio.'),
    ('unique_product_code', 'Código único', 'Ajusta códigos repetidos quando o recurso estiver ativo.'),
]

MEASURE_DEFAULT_FIELDS = [
    ('A', 'Altura', 'height_default', '2'),
    ('L', 'Largura', 'width_default', '11'),
    ('P', 'Profundidade', 'depth_default', '18'),
    ('C', 'Comprimento', 'length_default', '18'),
]

BASIC_DEFAULT_FIELDS = [
    ('Unidade', 'measure_unit_default', 'UN'),
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
    ('Vídeo', ''),
    ('Volumes', '1'),
]


def _rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def _clean_number_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip().replace(',', '.')
    if not text:
        return fallback
    try:
        number = float(text)
    except Exception:
        return text.replace('.', ',')
    if number.is_integer():
        return str(int(number))
    formatted = f'{number:.3f}'.rstrip('0').rstrip('.')
    return formatted.replace('.', ',')


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
    st.caption('Proteções técnicas já nascem ativas. Não alteram dados manuais, só limpam o CSV final.')
    updated = dict(rules)
    cols = st.columns(4)
    for index, (key, label, help_text) in enumerate(PROTECTION_FIELDS):
        with cols[index % 4]:
            updated[key] = st.toggle(label, value=bool(updated.get(key, True)), help=help_text, key=f'rules_center_{key}')
    updated['normalize_measures_to_meters'] = False
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    return updated


def _render_measure_rules(rules: dict[str, Any], custom_rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    st.markdown('#### Medidas padrão do produto')
    st.caption('Use números simples em centímetros. Exemplo: 2, 11 e 18. O sistema não transforma 18 em 0,018.')
    updated = dict(rules)
    custom_by_column = _custom_rules_by_column({'custom_rules': custom_rules})

    measure_enabled = st.toggle(
        'Usar medidas padrão quando a coluna existir e estiver vazia',
        value=True,
        key='rules_center_measure_defaults_enabled',
    )

    cols = st.columns(5)
    for index, (short_label, target_label, key, fallback) in enumerate(MEASURE_DEFAULT_FIELDS):
        current_value = _clean_number_text(updated.get(key), fallback)
        with cols[index]:
            value = st.text_input(short_label, value=current_value, key=f'rules_center_measure_value_{key}', help=target_label)
        value = _clean_number_text(value, fallback)
        updated[key] = value
        custom_rules = _upsert_system_rule(custom_rules, target_label, value, measure_enabled)

    with cols[4]:
        st.text_input('Unidade', value='Centímetro', disabled=True, key='rules_center_measure_unit_visible')
    updated['measure_unit_name_default'] = 'Centímetro'
    updated['normalize_measures_to_meters'] = False
    return updated, custom_rules


def _render_basic_defaults(rules: dict[str, Any], custom_rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated = dict(rules)
    custom_by_column = _custom_rules_by_column({'custom_rules': custom_rules})
    cols = st.columns(2)
    for index, (label, key, fallback) in enumerate(BASIC_DEFAULT_FIELDS):
        current_value = str(updated.get(key) or fallback)
        rule = custom_by_column.get(label.lower(), {})
        with cols[index % 2]:
            enabled = st.toggle(f'Usar {label}', value=bool(rule.get('enabled', True)), key=f'rules_center_basic_enabled_{key}')
            value = st.text_input(label, value=current_value, key=f'rules_center_basic_value_{key}')
        updated[key] = value
        custom_rules = _upsert_system_rule(custom_rules, label, value, enabled)
    return updated, custom_rules


def _render_extra_default_rules(custom_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with st.expander('Mostrar padrões finais opcionais', expanded=False):
        st.caption('São campos extras do modelo Bling. Só preenchem se a coluna existir e estiver vazia.')
        custom_by_column = _custom_rules_by_column({'custom_rules': custom_rules})
        for row_start in range(0, len(EXTRA_DEFAULT_RULES), 2):
            cols = st.columns(2)
            for col_index, (target, fallback) in enumerate(EXTRA_DEFAULT_RULES[row_start:row_start + 2]):
                rule = custom_by_column.get(target.lower(), {})
                with cols[col_index]:
                    enabled = st.toggle(f'Usar {target}', value=bool(rule.get('enabled', True)), key=f'rules_center_extra_enabled_{_rule_id(target)}')
                    value = st.text_input(target, value=str(rule.get('fill_value') if rule else fallback), key=f'rules_center_extra_value_{_rule_id(target)}')
                custom_rules = _upsert_system_rule(custom_rules, target, value, enabled)
    return custom_rules


def _render_default_rules(rules: dict[str, Any]) -> dict[str, Any]:
    updated = dict(rules)
    custom_rules = list(updated.get('custom_rules', []) or [])
    updated, custom_rules = _render_measure_rules(updated, custom_rules)
    st.divider()
    updated, custom_rules = _render_basic_defaults(updated, custom_rules)
    custom_rules = _render_extra_default_rules(custom_rules)
    updated['custom_rules'] = custom_rules
    return updated


def _save_rules_and_mark_ready(rules: dict[str, Any], *, source: str) -> None:
    set_user_rules(rules)
    st.session_state[RULES_CENTER_READY_KEY] = True
    add_audit_event(
        'rules_center_saved',
        area='REGRAS',
        step=str(st.session_state.get(WIZARD_STEP_KEY) or ''),
        details={
            'source': source,
            'ready_key': RULES_CENTER_READY_KEY,
            'ready': True,
            'responsible_file': 'bling_app_zero/ui/rules_center_step.py',
        },
    )


def _confirm_and_continue(rules: dict[str, Any]) -> None:
    _save_rules_and_mark_ready(rules, source='confirm_and_continue')
    current_step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()

    if current_step == STEP_REGRAS:
        st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
        st.session_state[RULES_CENTER_ADVANCED_KEY] = True
        add_audit_event(
            'rules_center_confirmed_and_advanced',
            area='REGRAS',
            step=STEP_REGRAS,
            details={
                'from': STEP_REGRAS,
                'to': STEP_ENTRADA,
                'wizard_step_key': WIZARD_STEP_KEY,
                'responsible_file': 'bling_app_zero/ui/rules_center_step.py',
            },
        )
        st.success('Central de regras confirmada. Avançando para Entrada dos dados...')
    else:
        add_audit_event(
            'rules_center_confirmed_without_navigation',
            area='REGRAS',
            step=current_step,
            details={
                'reason': 'rules_center_not_rendered_as_main_step',
                'current_step': current_step,
                'responsible_file': 'bling_app_zero/ui/rules_center_step.py',
            },
        )
        st.success('Central de regras confirmada.')

    st.rerun()


def render_rules_center_step() -> None:
    st.markdown('### Regras e Padrões')
    st.caption('Central visível do fluxo. Regras importantes não ficam escondidas na sidebar.')
    st.info('Regra principal: mapeamento/manual ganha. Padrões só completam células vazias depois do mapeamento.')

    rules = get_user_rules()
    rules = _render_protection_rules(rules)
    st.divider()
    rules = _render_default_rules(rules)

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar regras desta sessão', use_container_width=True, key='rules_center_save'):
            _save_rules_and_mark_ready(rules, source='save_button')
            st.success('Regras e padrões salvos para esta sessão.')
            st.rerun()
    with col_reset:
        if st.button('Restaurar padrões', use_container_width=True, key='rules_center_reset'):
            reset_user_rules()
            st.session_state[RULES_CENTER_READY_KEY] = True
            add_audit_event(
                'rules_center_reset_to_defaults',
                area='REGRAS',
                step=str(st.session_state.get(WIZARD_STEP_KEY) or ''),
                details={
                    'ready_key': RULES_CENTER_READY_KEY,
                    'ready': True,
                    'responsible_file': 'bling_app_zero/ui/rules_center_step.py',
                },
            )
            st.success('Padrões restaurados.')
            st.rerun()

    if st.button('Confirmar e continuar', use_container_width=True, key='rules_center_confirm'):
        _confirm_and_continue(rules)


def rules_center_ready() -> bool:
    return bool(st.session_state.get(RULES_CENTER_READY_KEY, False))


__all__ = [
    'RULES_CENTER_ADVANCED_KEY',
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
