from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.home_shared import df_signature, download_final, preview_df
from bling_app_zero.ui.layout import inject_mapping_css, render_mapping_title
from bling_app_zero.ui.mapping_ai_actions import render_ai_button
from bling_app_zero.ui.mapping_auto_suggestions import build_stock_auto_mapping
from bling_app_zero.ui.mapping_confidence_state import current_confidence_from_widgets, ordered_targets_once, required_targets
from bling_app_zero.ui.mapping_constants import EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION
from bling_app_zero.ui.mapping_field_widget import render_mapping_select
from bling_app_zero.ui.mapping_filters import filter_targets
from bling_app_zero.ui.mapping_models import estoque_model, source_columns_from_df, target_columns_from_model
from bling_app_zero.ui.mapping_pagination import render_mapping_page_arrows, visible_targets
from bling_app_zero.ui.mapping_preview_builder import build_estoque_preview
from bling_app_zero.ui.mapping_sidebar_rule_badge import sidebar_rule_targets_from_columns, with_sidebar_rule_badge
from bling_app_zero.ui.mapping_widget_state import clear_mapping_widgets, clear_stale_mapping_widgets, is_manual_value, mapping_base, target_widget_key


def _duplicated_source_columns(mapping: dict[str, str]) -> list[str]:
    used_values = [value for value in mapping.values() if value and not is_manual_value(value)]
    return sorted({value for value in used_values if value and used_values.count(value) > 1})


def _render_deposito_field(target: str, mapping_key: str, target_index: int, deposito: str, sidebar_rule_targets: set[str]) -> None:
    widget_key = target_widget_key(mapping_key, target_index)
    with st.container(border=True):
        render_mapping_title(with_sidebar_rule_badge('🟢 ' + target, sidebar_rule_targets))
        st.text_input(target, value=deposito, disabled=True, key=f'{widget_key}_dep', label_visibility='collapsed')


def _reset_stock_mapping(mapping_key: str, order_key: str) -> None:
    st.session_state.pop(mapping_key, None)
    st.session_state.pop('df_final_estoque_from_cadastro', None)
    st.session_state.pop('mapping_estoque_from_cadastro', None)
    st.session_state.pop('mapping_confidence_estoque_from_cadastro', None)
    st.session_state.pop(order_key, None)
    clear_mapping_widgets(mapping_key)
    st.rerun()


def render_manual_stock_mapping(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None, deposito: str) -> None:
    inject_mapping_css()

    model = estoque_model(df_modelo_estoque)
    source_columns = source_columns_from_df(df_source)
    target_columns = target_columns_from_model(model)
    sidebar_rule_targets = sidebar_rule_targets_from_columns(target_columns)
    options = [MANUAL_WRITE_OPTION, EMPTY_LEAVE_OPTION] + source_columns

    signature = df_signature(df_source) + ':' + '|'.join(target_columns) + f':{deposito}'
    mapping_key = mapping_base('stk_map_', signature)
    order_key = f'{mapping_key}_order'

    clear_stale_mapping_widgets(mapping_key)
    if mapping_key not in st.session_state:
        st.session_state[mapping_key] = build_stock_auto_mapping(df_source, model)
        st.session_state.pop(order_key, None)

    st.markdown('##### Conferir campos do estoque')
    st.caption('🔴 precisa escolher · 🟡 conferir · 🟢 pronto, valor fixo ou vazio confirmado · 🟣 regra/recurso do sidebar')
    with st.expander('Ver origem do estoque', expanded=False):
        preview_df('Origem para estoque', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Pedir ajuda da IA no estoque')

    current_confidence = current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = ordered_targets_once(order_key, target_columns, current_confidence)
    required = required_targets(target_columns)
    filtered_targets = filter_targets(mapping_key, ordered_targets, current_confidence, required, sidebar_rule_targets)
    visible = visible_targets(mapping_key, filtered_targets)

    target_index_by_name = {target: index for index, target in enumerate(target_columns)}
    edited_mapping: dict[str, str] = {target: current_mapping.get(target, '') for target in target_columns}
    edited_confidence: dict[str, dict[str, object]] = current_confidence.copy()

    for target in visible:
        target_index = target_index_by_name.get(target, len(edited_mapping))
        target_key = normalize_key(target)
        if 'deposito' in target_key:
            _render_deposito_field(target, mapping_key, target_index, deposito, sidebar_rule_targets)
            edited_mapping[target] = ''
            edited_confidence[target] = {'level': 'verde', 'emoji': '🟢', 'label': 'pronto', 'score': 100, 'order': 2}
            continue

        selected, info_after = render_mapping_select(
            df_source,
            target,
            target_index,
            current_mapping.get(target, ''),
            mapping_key,
            options,
        )
        edited_mapping[target] = selected
        edited_confidence[target] = info_after

    render_mapping_page_arrows(mapping_key)

    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_estoque_from_cadastro'] = edited_confidence

    df_preview_manual = build_estoque_preview(df_source, model, edited_mapping, target_columns, mapping_key, deposito)
    st.session_state['df_final_estoque_from_cadastro'] = df_preview_manual
    st.session_state['mapping_estoque_from_cadastro'] = edited_mapping

    duplicated = _duplicated_source_columns(edited_mapping)
    if duplicated:
        st.warning('A mesma coluna da origem foi usada mais de uma vez no estoque: ' + ', '.join(duplicated))

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar prévia do estoque', use_container_width=True, key=f'{mapping_key}_refresh'):
            st.rerun()
    with col_b:
        if st.button('Refazer sugestões do estoque', use_container_width=True, key=f'{mapping_key}_reset'):
            _reset_stock_mapping(mapping_key, order_key)


def render_dual_stock_output(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None) -> None:
    st.markdown('#### Estoque')
    if not isinstance(df_modelo_estoque, pd.DataFrame) or not len(df_modelo_estoque.columns):
        st.info('Envie o modelo de estoque no passo inicial para gerar também o CSV de estoque.')
        return

    deposito = str(st.session_state.get('deposito_manual') or '').strip()
    if not deposito:
        st.warning('Informe o depósito no passo inicial para preencher o modelo de estoque.')
        return

    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)
    df_stock = st.session_state.get('df_final_estoque_from_cadastro')
    if isinstance(df_stock, pd.DataFrame) and not df_stock.empty:
        preview_df('Prévia do estoque', df_stock)
        download_final(df_stock, 'estoque')


__all__ = ['render_dual_stock_output', 'render_manual_stock_mapping']
