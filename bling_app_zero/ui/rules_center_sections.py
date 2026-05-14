from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.rule_value_validator import rule_value_warning
from bling_app_zero.core.user_rules import remove_custom_rule_by_id

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
    ('Categoria', 'Vazio'),
    ('Clonar dados do pai', 'Não'),
    ('Condição do produto', 'Novo'),
    ('Descrição Complementar', 'Vazio'),
    ('Frete Grátis', 'Não'),
    ('Informações Adicionais', 'Vazio'),
    ('Situação', 'Ativo'),
    ('Vídeo', 'Vazio'),
    ('Volumes', '1'),
]

DEFAULT_RULES_ENABLED_KEY = 'rules_center_default_rules_enabled'
CUSTOM_RULE_NOTICE_KEY = 'rules_center_custom_rule_notice'
NEW_RULE_VERSION_KEY = 'rules_center_new_rule_version'


def rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def user_rule_id(index: int, target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'usr_{index}_{safe or "rule"}'[:96]


def render_rule_value_warning(target: str, value: Any) -> None:
    warning = rule_value_warning(target, value)
    if warning:
        st.warning(warning)


def clean_number_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip().replace(',', '.')
    if not text:
        return fallback
    try:
        number = float(text)
    except Exception:
        return text.replace('.', ',')
    if number.is_integer():
        return str(int(number))
    return f'{number:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


def custom_rules_by_column(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rule in rules.get('custom_rules', []) or []:
        if not isinstance(rule, dict):
            continue
        target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if target:
            out[target.lower()] = dict(rule)
    return out


def _value_or_fallback(rule: dict[str, Any], fallback: str) -> str:
    value = str(rule.get('fill_value', '') if rule else '').strip()
    return value if value else fallback


def _rule_key(rule: dict[str, Any], index: int) -> str:
    saved = str(rule.get('id') or '').strip()
    if saved:
        return saved
    return user_rule_id(index, str(rule.get('target_column') or rule.get('condition') or 'regra'))


def _is_system_rule(rule: dict[str, Any]) -> bool:
    return str(rule.get('source') or '').strip().lower() == 'system'


def upsert_system_rule(custom_rules: list[dict[str, Any]], target_column: str, fill_value: str, enabled: bool) -> list[dict[str, Any]]:
    target_key = target_column.strip().lower()
    updated: list[dict[str, Any]] = []
    found = False
    for rule in custom_rules:
        if not isinstance(rule, dict):
            continue
        current_target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if current_target.lower() == target_key:
            current = dict(rule)
            current['id'] = str(current.get('id') or rule_id(target_column))
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
                'id': rule_id(target_column),
                'condition': target_column,
                'target_column': target_column,
                'fill_value': str(fill_value or ''),
                'only_when_empty': True,
                'enabled': bool(enabled),
                'source': 'system',
            }
        )
    return updated


def _all_default_targets() -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = [
        ('Altura', '2'),
        ('Largura', '11'),
        ('Profundidade', '18'),
        ('Comprimento', '18'),
        ('Unidade das medidas', 'Centímetro'),
    ]
    targets.extend((label, fallback) for label, _key, fallback in BASIC_DEFAULT_FIELDS)
    targets.extend(EXTRA_DEFAULT_RULES)
    return targets


def _disable_all_default_rules(custom_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated = list(custom_rules or [])
    custom_by_column = custom_rules_by_column({'custom_rules': updated})
    for target, fallback in _all_default_targets():
        rule = custom_by_column.get(target.lower(), {})
        value = _value_or_fallback(rule, fallback)
        updated = upsert_system_rule(updated, target, value, False)
    return updated


def disable_all_rules(rules: dict[str, Any]) -> dict[str, Any]:
    updated = dict(rules)
    updated['clean_invalid_gtin'] = False
    updated['normalize_image_separator'] = False
    updated['auto_product_code'] = False
    updated['unique_product_code'] = False
    updated['normalize_measures_to_meters'] = False
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = [
        {**dict(rule), 'enabled': False}
        for rule in list(updated.get('custom_rules', []) or [])
        if isinstance(rule, dict)
    ]
    updated['custom_rules'] = _disable_all_default_rules(updated['custom_rules'])
    return updated


def render_protection_rules(rules: dict[str, Any]) -> dict[str, Any]:
    st.markdown('#### Proteções do CSV final')
    st.caption('Ligue ou desligue os recursos que tratam o arquivo final.')
    updated = dict(rules)
    cols = st.columns(4)
    for index, (key, label, help_text) in enumerate(PROTECTION_FIELDS):
        with cols[index % 4]:
            updated[key] = st.toggle(label, value=bool(updated.get(key, True)), help=help_text, key=f'rules_center_{key}')
    updated['normalize_measures_to_meters'] = False
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    return updated


def render_measure_rules(rules: dict[str, Any], custom_rules: list[dict[str, Any]], master_enabled: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    st.markdown('#### Medidas padrão do produto')
    st.caption('Campos editáveis com liga/desliga real. P/C alimenta Profundidade e Comprimento.')
    updated = dict(rules)
    measure_enabled = st.toggle(
        'Usar medidas padrão quando a coluna existir e estiver vazia',
        value=bool(master_enabled),
        disabled=not master_enabled,
        key='rules_center_measure_defaults_enabled',
    )
    unit_measure_enabled = st.toggle(
        'Usar unidade das medidas',
        value=bool(master_enabled),
        disabled=not master_enabled,
        key='rules_center_measure_unit_enabled',
    )
    cols = st.columns(4)

    for index, (short_label, target_label, key, fallback) in enumerate(MEASURE_DEFAULT_FIELDS):
        current_value = clean_number_text(updated.get(key), fallback)
        with cols[index]:
            value = st.text_input(short_label, value=current_value, key=f'rules_center_measure_value_{key}', help=target_label, disabled=not master_enabled)
            render_rule_value_warning(target_label, value)
        value = clean_number_text(value, fallback)
        updated[key] = value
        custom_rules = upsert_system_rule(custom_rules, target_label, value, bool(master_enabled and measure_enabled))

    depth_value = clean_number_text(updated.get('depth_default'), '18')
    length_value = clean_number_text(updated.get('length_default'), depth_value or '18')
    pc_value = depth_value if depth_value == length_value else depth_value or length_value or '18'
    with cols[2]:
        pc_value = st.text_input('P/C', value=pc_value, key='rules_center_measure_value_depth_length_default', help='Profundidade e Comprimento', disabled=not master_enabled)
        render_rule_value_warning('Profundidade/Comprimento', pc_value)
    pc_value = clean_number_text(pc_value, '18')
    updated['depth_default'] = pc_value
    updated['length_default'] = pc_value
    custom_rules = upsert_system_rule(custom_rules, 'Profundidade', pc_value, bool(master_enabled and measure_enabled))
    custom_rules = upsert_system_rule(custom_rules, 'Comprimento', pc_value, bool(master_enabled and measure_enabled))

    with cols[3]:
        unit_name = st.text_input('Unidade medidas', value=str(updated.get('measure_unit_name_default') or 'Centímetro'), key='rules_center_measure_unit_name_value', help='Unidade das dimensões: Centímetro, Metro, Milímetro ou VAZIO', disabled=not master_enabled)
        render_rule_value_warning('Unidade das medidas', unit_name)
    updated['measure_unit_name_default'] = str(unit_name or '').strip()
    custom_rules = upsert_system_rule(custom_rules, 'Unidade das medidas', updated['measure_unit_name_default'], bool(master_enabled and unit_measure_enabled))
    updated['normalize_measures_to_meters'] = False
    return updated, custom_rules


def render_basic_defaults(rules: dict[str, Any], custom_rules: list[dict[str, Any]], master_enabled: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    st.markdown('#### Padrões básicos')
    st.caption('Preenchem somente se a coluna existir e estiver vazia.')
    updated = dict(rules)
    custom_by_column = custom_rules_by_column({'custom_rules': custom_rules})
    cols = st.columns(2)
    for index, (label, key, fallback) in enumerate(BASIC_DEFAULT_FIELDS):
        current_value = str(updated.get(key) or fallback)
        rule = custom_by_column.get(label.lower(), {})
        if rule:
            current_value = _value_or_fallback(rule, current_value)
        with cols[index % 2]:
            enabled = st.toggle(f'Usar {label}', value=bool(master_enabled and rule.get('enabled', master_enabled)), disabled=not master_enabled, key=f'rules_center_basic_enabled_{key}')
            value = st.text_input(label, value=current_value, key=f'rules_center_basic_value_{key}', disabled=not master_enabled)
            render_rule_value_warning(label, value)
        updated[key] = value
        custom_rules = upsert_system_rule(custom_rules, label, value, bool(master_enabled and enabled))
    return updated, custom_rules


def render_extra_default_rules(custom_rules: list[dict[str, Any]], master_enabled: bool = True) -> list[dict[str, Any]]:
    st.markdown('#### Padrões finais')
    st.caption('Campos extras do modelo Bling. Ficam visíveis para revisão e só preenchem células vazias.')
    custom_by_column = custom_rules_by_column({'custom_rules': custom_rules})
    for row_start in range(0, len(EXTRA_DEFAULT_RULES), 2):
        cols = st.columns(2)
        for col_index, (target, fallback) in enumerate(EXTRA_DEFAULT_RULES[row_start:row_start + 2]):
            rule = custom_by_column.get(target.lower(), {})
            with cols[col_index]:
                enabled = st.toggle(f'Usar {target}', value=bool(master_enabled and rule.get('enabled', master_enabled)), disabled=not master_enabled, key=f'rules_center_extra_enabled_{rule_id(target)}')
                value = st.text_input(target, value=_value_or_fallback(rule, fallback), key=f'rules_center_extra_value_{rule_id(target)}', disabled=not master_enabled)
                render_rule_value_warning(target, value)
            custom_rules = upsert_system_rule(custom_rules, target, value, bool(master_enabled and enabled))
    return custom_rules


def _render_default_rules_body(updated: dict[str, Any], custom_rules: list[dict[str, Any]], master_enabled: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not master_enabled:
        st.caption('Regras opcionais desligadas. Medidas, padrões básicos e padrões finais não serão aplicados. As Proteções do CSV final continuam funcionando separadamente.')
        return updated, _disable_all_default_rules(custom_rules)

    updated, custom_rules = render_measure_rules(updated, custom_rules, master_enabled=True)
    st.divider()
    updated, custom_rules = render_basic_defaults(updated, custom_rules, master_enabled=True)
    st.divider()
    custom_rules = render_extra_default_rules(custom_rules, master_enabled=True)
    return updated, custom_rules


def _render_custom_rule_card(rule: dict[str, Any], index: int, master_enabled: bool) -> dict[str, Any] | None:
    current = dict(rule)
    key = _rule_key(current, index)
    target = str(current.get('target_column') or current.get('condition') or '').strip()
    value = str(current.get('fill_value') or '')
    enabled = bool(current.get('enabled', True))
    only_empty = bool(current.get('only_when_empty', False))

    with st.container(border=True):
        col_status, col_delete = st.columns([3, 1])
        with col_status:
            enabled = st.toggle('Aplicar esta regra', value=bool(master_enabled and enabled), disabled=not master_enabled, key=f'rules_center_user_enabled_{key}')
        with col_delete:
            if st.button('Excluir', use_container_width=True, key=f'rules_center_user_delete_{key}'):
                remove_custom_rule_by_id(str(current.get('id') or key))
                st.session_state[CUSTOM_RULE_NOTICE_KEY] = 'Regra excluída.'
                st.rerun()

        target = st.text_input('Coluna de destino no Bling', value=target, key=f'rules_center_user_target_{key}', disabled=not master_enabled)
        value = st.text_input('Valor para preencher', value=value, key=f'rules_center_user_value_{key}', disabled=not master_enabled)
        only_empty = st.toggle('Somente quando estiver vazio', value=only_empty, disabled=not master_enabled, key=f'rules_center_user_empty_{key}')
        render_rule_value_warning(target, value)

    target = str(target or '').strip()
    if not target:
        st.warning('Regra personalizada sem coluna de destino será ignorada.')
        return None

    current['id'] = str(current.get('id') or key)
    current['condition'] = target
    current['target_column'] = target
    current['fill_value'] = str(value or '')
    current['only_when_empty'] = bool(only_empty)
    current['enabled'] = bool(master_enabled and enabled)
    current['source'] = 'user'
    return current


def render_custom_rules(custom_rules: list[dict[str, Any]], master_enabled: bool = True) -> list[dict[str, Any]]:
    st.markdown('#### Regras personalizadas')
    st.caption('Crie quantas regras precisar. Cada regra pode ser ligada, editada ou excluída aqui. Não há mais edição duplicada na sidebar.')

    notice = st.session_state.pop(CUSTOM_RULE_NOTICE_KEY, '')
    if notice:
        st.success(notice)

    system_rules = [dict(rule) for rule in custom_rules if isinstance(rule, dict) and _is_system_rule(rule)]
    user_rules = [dict(rule) for rule in custom_rules if isinstance(rule, dict) and not _is_system_rule(rule)]

    updated_user_rules: list[dict[str, Any]] = []
    if user_rules:
        for index, rule in enumerate(user_rules):
            rendered = _render_custom_rule_card(rule, index, master_enabled)
            if rendered:
                updated_user_rules.append(rendered)
    else:
        st.caption('Nenhuma regra personalizada criada ainda.')

    version = int(st.session_state.get(NEW_RULE_VERSION_KEY, 0) or 0)
    target_key = f'rules_center_new_rule_target_{version}'
    value_key = f'rules_center_new_rule_value_{version}'
    empty_key = f'rules_center_new_rule_only_empty_{version}'

    with st.container(border=True):
        st.markdown('**Nova regra**')
        new_target = st.text_input('Coluna da nova regra', key=target_key, placeholder='Ex: Tipo')
        new_value = st.text_input('Valor da nova regra', key=value_key, placeholder='Ex: Produto')
        new_only_empty = st.toggle('Aplicar somente quando estiver vazio', value=True, key=empty_key)
        if st.button('Adicionar nova regra', use_container_width=True, key='rules_center_add_custom_rule', disabled=not master_enabled):
            target = str(new_target or '').strip()
            if not target:
                st.warning('Informe a coluna da nova regra.')
            else:
                new_rule = {
                    'id': user_rule_id(len(updated_user_rules) + 1, target),
                    'condition': target,
                    'target_column': target,
                    'fill_value': str(new_value or ''),
                    'only_when_empty': bool(new_only_empty),
                    'enabled': True,
                    'source': 'user',
                }
                updated_user_rules.append(new_rule)
                st.session_state[NEW_RULE_VERSION_KEY] = version + 1
                st.session_state[CUSTOM_RULE_NOTICE_KEY] = 'Regra adicionada.'
                st.rerun()

    return system_rules + updated_user_rules


def render_default_rules(rules: dict[str, Any]) -> dict[str, Any]:
    updated = dict(rules)
    custom_rules = list(updated.get('custom_rules', []) or [])

    if DEFAULT_RULES_ENABLED_KEY not in st.session_state:
        has_enabled_custom = any(bool(rule.get('enabled')) for rule in custom_rules if isinstance(rule, dict))
        st.session_state[DEFAULT_RULES_ENABLED_KEY] = bool(has_enabled_custom)

    st.markdown('#### Padrões opcionais do produto')
    st.caption('Tudo fica centralizado aqui: medidas, padrões básicos, padrões finais e regras personalizadas.')
    col_toggle, col_disable = st.columns([2, 1])
    with col_toggle:
        master_enabled = st.toggle(
            'Usar regras opcionais de preenchimento',
            value=bool(st.session_state.get(DEFAULT_RULES_ENABLED_KEY, False)),
            key=DEFAULT_RULES_ENABLED_KEY,
            help='Liga ou desliga Medidas padrão do produto, Padrões básicos, Padrões finais e Regras personalizadas. Não altera as Proteções do CSV final.',
        )
    with col_disable:
        if st.button('Desligar opcionais', use_container_width=True, key='rules_center_disable_optional_rules'):
            st.session_state[DEFAULT_RULES_ENABLED_KEY] = False
            updated['custom_rules'] = _disable_all_default_rules(custom_rules)
            st.session_state[CUSTOM_RULE_NOTICE_KEY] = 'Regras opcionais desligadas.'
            st.rerun()

    updated, custom_rules = _render_default_rules_body(updated, custom_rules, master_enabled)
    st.divider()
    custom_rules = render_custom_rules(custom_rules, master_enabled=master_enabled)

    updated['custom_rules'] = custom_rules
    return updated


__all__ = [
    'DEFAULT_RULES_ENABLED_KEY',
    'disable_all_rules',
    'render_basic_defaults',
    'render_custom_rules',
    'render_default_rules',
    'render_extra_default_rules',
    'render_measure_rules',
    'render_protection_rules',
]
