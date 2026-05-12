from __future__ import annotations

import json
from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import normalize_key
from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules
from bling_app_zero.ui.home_wizard_constants import STEP_ENTRADA, STEP_REGRAS, WIZARD_STEP_KEY

RULES_CENTER_READY_KEY = 'rules_center_reviewed'
RULES_CENTER_ADVANCED_KEY = 'rules_center_advanced_to_next_step'
RULES_CENTER_AUTOSAVE_SIGNATURE_KEY = 'rules_center_autosave_signature'

EMPTY_RULE_MARKERS = {'vazio', '#vazio', '__vazio__', 'em branco', 'embranco', 'branco', 'limpar', 'sem informacao', 'seminformacao'}

PROTECTION_FIELDS = [
    ('clean_invalid_gtin', 'GTIN inválido', 'GTIN fora do padrão sai vazio no arquivo final.'),
    ('normalize_image_separator', 'Imagens por |', 'Múltiplas imagens saem como img1|img2|img3.'),
    ('auto_product_code', 'Código automático', 'Preenche código/SKU somente quando o campo estiver vazio.'),
    ('unique_product_code', 'Código único', 'Ajusta códigos repetidos quando o recurso estiver ativo.'),
]

MEASURE_DEFAULT_FIELDS = [
    ('A', 'Altura', 'height_default', '2'),
    ('L', 'Largura', 'width_default', '11'),
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


def _rules_signature(rules: dict[str, Any]) -> str:
    try:
        return json.dumps(rules, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(rules)


def _is_empty_command(value: Any) -> bool:
    return normalize_key(value) in EMPTY_RULE_MARKERS


def _is_number(value: Any) -> bool:
    text = str(value if value is not None else '').strip().replace(',', '.')
    if not text:
        return False
    try:
        float(text)
        return True
    except Exception:
        return False


def _rule_value_warning(target: str, value: Any) -> str:
    target_key = normalize_key(target)
    text = str(value if value is not None else '').strip()
    value_key = normalize_key(text)
    if not text or _is_empty_command(text):
        return ''
    if any(term in target_key for term in ('altura', 'largura', 'profundidade', 'comprimento')):
        return '' if _is_number(text) else f'O valor "{text}" parece incoerente para {target}. Use número em centímetros ou VAZIO.'
    if target_key in {'itens por caixa', 'itens p caixa', 'itens p/ caixa', 'volumes'}:
        return '' if _is_number(text) else f'O valor "{text}" parece incoerente para {target}. Use número ou VAZIO.'
    if target_key in {'frete gratis', 'frete grátis', 'clonar dados do pai'}:
        return '' if value_key in {'sim', 'nao', 'não', 's', 'n'} else f'O valor "{text}" parece incoerente para {target}. Use Sim, Não ou VAZIO.'
    if target_key in {'situacao', 'situação'}:
        return '' if value_key in {'ativo', 'inativo', 'excluido', 'excluído'} else f'O valor "{text}" parece incoerente para {target}. Use Ativo, Inativo ou VAZIO.'
    if target_key in {'condicao do produto', 'condição do produto'}:
        return '' if value_key in {'novo', 'usado', 'recondicionado'} else f'O valor "{text}" parece incoerente para {target}. Use Novo, Usado ou VAZIO.'
    if target_key == 'unidade':
        return f'O valor "{text}" parece incoerente para Unidade. Use algo como UN, PC, CX ou VAZIO.' if _is_number(text) or len(text) > 8 else ''
    if target_key == 'categoria':
        return f'O valor "{text}" parece incoerente para Categoria. Use nome de categoria ou VAZIO.' if _is_number(text) else ''
    if target_key in {'video', 'vídeo'}:
        lower = text.lower()
        return '' if lower.startswith(('http://', 'https://')) else f'O valor "{text}" parece incoerente para Vídeo. Use URL ou VAZIO.'
    return ''


def _render_rule_value_warning(target: str, value: Any) -> None:
    warning = _rule_value_warning(target, value)
    if warning:
        st.warning(warning)


def _clear_mapping_rule_cache() -> None:
    prefixes_to_clear = ('cad_map_', 'stk_map_', 'mapping_confidence_')
    exact_keys = {'mapping_confidence_cadastro', 'mapping_confidence_estoque_from_cadastro'}
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if text_key.startswith('rules_center_'):
            continue
        if text_key in exact_keys or text_key.endswith('_order') or text_key.startswith(prefixes_to_clear):
            st.session_state.pop(key, None)


def _auto_save_rules_if_changed(rules: dict[str, Any], previous_signature: str) -> None:
    normalized = set_user_rules(rules)
    current_signature = _rules_signature(normalized)
    saved_signature = str(st.session_state.get(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY) or previous_signature or '')
    if current_signature == saved_signature:
        st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = current_signature
        return
    st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = current_signature
    st.session_state[RULES_CENTER_READY_KEY] = True
    _clear_mapping_rule_cache()
    add_audit_event('rules_center_autosaved_instant', area='REGRAS', step=str(st.session_state.get(WIZARD_STEP_KEY) or ''), details={'ready_key': RULES_CENTER_READY_KEY, 'ready': True, 'effect': 'mapping_rule_badges_recomputed_immediately', 'responsible_file': 'bling_app_zero/ui/rules_center_step.py'})
    st.rerun()


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
        updated.append({'id': _rule_id(target_column), 'condition': target_column, 'target_column': target_column, 'fill_value': str(fill_value or ''), 'only_when_empty': True, 'enabled': bool(enabled), 'source': 'system'})
    return updated


def _render_protection_rules(rules: dict[str, Any]) -> dict[str, Any]:
    st.markdown('#### Proteções do CSV final')
    st.caption('Alterou uma proteção? O mapeamento recalcula os faróis automaticamente.')
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
    measure_enabled = st.toggle('Usar medidas padrão quando a coluna existir e estiver vazia', value=True, key='rules_center_measure_defaults_enabled')
    cols = st.columns(4)
    for index, (short_label, target_label, key, fallback) in enumerate(MEASURE_DEFAULT_FIELDS):
        current_value = _clean_number_text(updated.get(key), fallback)
        with cols[index]:
            value = st.text_input(short_label, value=current_value, key=f'rules_center_measure_value_{key}', help=target_label)
            _render_rule_value_warning(target_label, value)
        value = _clean_number_text(value, fallback)
        updated[key] = value
        custom_rules = _upsert_system_rule(custom_rules, target_label, value, measure_enabled)
    depth_value = _clean_number_text(updated.get('depth_default'), '18')
    length_value = _clean_number_text(updated.get('length_default'), depth_value or '18')
    pc_value = depth_value if depth_value == length_value else depth_value or length_value or '18'
    with cols[2]:
        pc_value = st.text_input('P/C', value=pc_value, key='rules_center_measure_value_depth_length_default', help='Profundidade e Comprimento')
        _render_rule_value_warning('Profundidade/Comprimento', pc_value)
    pc_value = _clean_number_text(pc_value, '18')
    updated['depth_default'] = pc_value
    updated['length_default'] = pc_value
    custom_rules = _upsert_system_rule(custom_rules, 'Profundidade', pc_value, measure_enabled)
    custom_rules = _upsert_system_rule(custom_rules, 'Comprimento', pc_value, measure_enabled)
    with cols[3]:
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
            _render_rule_value_warning(label, value)
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
                    _render_rule_value_warning(target, value)
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
    normalized = set_user_rules(rules)
    st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = _rules_signature(normalized)
    st.session_state[RULES_CENTER_READY_KEY] = True
    _clear_mapping_rule_cache()
    add_audit_event('rules_center_saved', area='REGRAS', step=str(st.session_state.get(WIZARD_STEP_KEY) or ''), details={'source': source, 'ready_key': RULES_CENTER_READY_KEY, 'ready': True, 'responsible_file': 'bling_app_zero/ui/rules_center_step.py'})


def _confirm_and_continue(rules: dict[str, Any]) -> None:
    _save_rules_and_mark_ready(rules, source='confirm_and_continue')
    current_step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    if current_step == STEP_REGRAS:
        st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
        st.session_state[RULES_CENTER_ADVANCED_KEY] = True
        add_audit_event('rules_center_confirmed_and_advanced', area='REGRAS', step=STEP_REGRAS, details={'from': STEP_REGRAS, 'to': STEP_ENTRADA, 'wizard_step_key': WIZARD_STEP_KEY, 'responsible_file': 'bling_app_zero/ui/rules_center_step.py'})
        st.success('Central de regras confirmada. Avançando para Entrada dos dados...')
    else:
        add_audit_event('rules_center_confirmed_without_navigation', area='REGRAS', step=current_step, details={'reason': 'rules_center_not_rendered_as_main_step', 'current_step': current_step, 'responsible_file': 'bling_app_zero/ui/rules_center_step.py'})
        st.success('Central de regras confirmada.')
    st.rerun()


def render_rules_center_step() -> None:
    st.markdown('### Regras e Padrões')
    st.caption('Central visível do fluxo. Regras importantes não ficam escondidas na sidebar.')
    st.info('Regra principal: mapeamento/manual ganha. Padrões só completam células vazias depois do mapeamento.')
    original_rules = get_user_rules()
    previous_signature = _rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)
    rules = _render_protection_rules(original_rules)
    st.divider()
    rules = _render_default_rules(rules)
    _auto_save_rules_if_changed(rules, previous_signature)
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar regras desta sessão', use_container_width=True, key='rules_center_save'):
            _save_rules_and_mark_ready(rules, source='save_button')
            st.success('Regras e padrões salvos para esta sessão.')
            st.rerun()
    with col_reset:
        if st.button('Restaurar padrões', use_container_width=True, key='rules_center_reset'):
            normalized = reset_user_rules()
            st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = _rules_signature(normalized)
            st.session_state[RULES_CENTER_READY_KEY] = True
            _clear_mapping_rule_cache()
            add_audit_event('rules_center_reset_to_defaults', area='REGRAS', step=str(st.session_state.get(WIZARD_STEP_KEY) or ''), details={'ready_key': RULES_CENTER_READY_KEY, 'ready': True, 'responsible_file': 'bling_app_zero/ui/rules_center_step.py'})
            st.success('Padrões restaurados.')
            st.rerun()
    if st.button('Confirmar e continuar', use_container_width=True, key='rules_center_confirm'):
        _confirm_and_continue(rules)


def rules_center_ready() -> bool:
    return bool(st.session_state.get(RULES_CENTER_READY_KEY, False))


__all__ = ['RULES_CENTER_ADVANCED_KEY', 'RULES_CENTER_READY_KEY', 'render_rules_center_step', 'rules_center_ready']
