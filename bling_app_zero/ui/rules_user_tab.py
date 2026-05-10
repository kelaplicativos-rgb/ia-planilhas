from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    reset_user_rules,
    set_custom_rule_enabled,
    update_custom_rule_by_id,
)

NOTICE_KEY = 'rules_notice_clean'


def _inject_rules_style() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) {
            padding: 0.72rem 0.72rem 0.42rem 0.72rem !important;
            margin: 0.55rem 0 0.78rem 0 !important;
            border: 1px solid rgba(37, 99, 235, 0.20) !important;
            border-left: 4px solid rgba(37, 99, 235, 0.72) !important;
            border-radius: 16px !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.96)) !important;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.045) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) input {
            min-height: 39px !important;
            border-radius: 12px !important;
            border: 1px solid rgba(37, 99, 235, 0.26) !important;
            background: #ffffff !important;
            color: var(--bling-text) !important;
            font-size: 0.93rem !important;
            font-weight: 650 !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) p {
            margin-bottom: 0.12rem !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) div[data-testid="stToggle"] {
            margin-top: -0.12rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _notice(text: str) -> None:
    st.session_state[NOTICE_KEY] = text


def _show_notice() -> None:
    text = st.session_state.pop(NOTICE_KEY, '')
    if text:
        st.caption(f'Salvo: {text}')


def _rule_id(rule: dict, index: int) -> str:
    saved = str(rule.get('id') or '').strip()
    if saved:
        return saved
    target = str(rule.get('target_column') or f'item_{index}').strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in target).strip('_')
    return f'rule_{index}_{safe or "item"}'


def _is_system(rule: dict) -> bool:
    return str(rule.get('source') or '').strip().lower() == 'system'


def _group(rule: dict) -> str:
    target = str(rule.get('target_column') or '').strip().lower()
    if target in {'fornecedor', 'nome fornecedor', 'nome do fornecedor'}:
        return 'fornecedor'
    if target in {'unidade', 'unidade de medida', 'unidade medida'}:
        return 'unidade'
    return target


def _visible_system_rules(rules: list[dict]) -> list[dict]:
    visible: list[dict] = []
    seen: set[str] = set()
    for rule in rules:
        group = _group(rule)
        if group in seen:
            continue
        seen.add(group)
        visible.append(rule)
    return visible


def _save_enabled(rule_id: str, current: bool, new_value: bool) -> None:
    if new_value == current:
        return
    set_custom_rule_enabled(rule_id, new_value)
    _notice('status atualizado')
    st.rerun()


def _save_value(rule_id: str, target: str, current: str, new_value: str, only_empty: bool) -> None:
    if str(new_value) == str(current):
        return
    update_custom_rule_by_id(rule_id, target, str(new_value), only_empty)
    _notice('valor atualizado')
    st.rerun()


def _render_rule_card(rule: dict, index: int) -> None:
    rule_id = _rule_id(rule, index)
    target = str(rule.get('target_column') or '').strip() or 'Coluna sem nome'
    current_value = str(rule.get('fill_value') or '')
    current_enabled = bool(rule.get('enabled', True))
    only_empty = bool(rule.get('only_when_empty', False))

    with st.container():
        st.markdown(f'**{target}**')
        value = st.text_input(
            'valor',
            value=current_value,
            key=f'rule_value_{rule_id}',
            placeholder='Digite o valor padrão',
            label_visibility='collapsed',
        )
        enabled = st.toggle(
            'Aplicar no arquivo final',
            value=current_enabled,
            key=f'rule_enabled_{rule_id}',
        )

    _save_value(rule_id, target, current_value, value, only_empty)
    _save_enabled(rule_id, current_enabled, enabled)


def _render_system_rules(system_rules: list[dict]) -> None:
    st.markdown('##### Padrões')
    st.caption('Valores fixos aplicados automaticamente.')
    visible = _visible_system_rules(system_rules)
    if not visible:
        st.caption('Nenhum padrão carregado.')
        return
    for index, rule in enumerate(visible):
        _render_rule_card(rule, index)


def _render_custom_rules(user_rules: list[dict], start_index: int) -> None:
    st.markdown('##### Personalizadas')
    if not user_rules:
        st.caption('Nenhuma regra personalizada.')
        return
    for offset, rule in enumerate(user_rules):
        _render_rule_card(rule, start_index + offset)


def _render_new_rule() -> None:
    st.markdown('##### Nova regra')
    target = st.text_input('Coluna', key='new_rule_target', placeholder='Ex: Tipo')
    value = st.text_input('Valor', key='new_rule_value', placeholder='Ex: Produto')
    if st.button('Adicionar regra', use_container_width=True, key='add_rule_clean'):
        target_text = str(target or '').strip()
        if not target_text:
            st.warning('Informe a coluna.')
            return
        add_custom_rule(target_text, target_text, str(value or ''), False)
        st.session_state['new_rule_target'] = ''
        st.session_state['new_rule_value'] = ''
        _notice('regra adicionada')
        st.rerun()


def render_user_rules_tab() -> None:
    _inject_rules_style()
    rules = get_user_rules()
    all_rules = list(rules.get('custom_rules', []))
    system_rules = [rule for rule in all_rules if _is_system(rule)]
    user_rules = [rule for rule in all_rules if not _is_system(rule)]
    visible_system = _visible_system_rules(system_rules)

    st.markdown('##### Regras')
    st.caption('Preenchimentos automáticos do arquivo final.')
    _show_notice()
    _render_system_rules(system_rules)
    st.divider()
    _render_custom_rules(user_rules, len(visible_system))
    st.divider()
    _render_new_rule()
    st.divider()
    if st.button('Restaurar padrão', use_container_width=True, key='reset_rules_clean'):
        reset_user_rules()
        _notice('padrão restaurado')
        st.rerun()
