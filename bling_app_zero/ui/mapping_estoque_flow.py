from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_wizard_state import (
    ESTOQUE_CONFIDENCE_KEY,
    ESTOQUE_FINAL_KEY,
    ESTOQUE_MAPPING_KEY,
    LEGACY_ESTOQUE_CONFIDENCE_KEY,
    LEGACY_ESTOQUE_FINAL_KEY,
    LEGACY_ESTOQUE_MAPPING_KEY,
    set_stock_output,
    stock_final_df,
)
from bling_app_zero.ui.home_autofluxo import pause_home_autofluxo_for_manual_review
from bling_app_zero.ui.home_shared import df_signature, download_final, preview_df
from bling_app_zero.ui.home_wizard_scroll import render_mapping_fields_anchor
from bling_app_zero.ui.layout import inject_mapping_css
from bling_app_zero.ui.mapping_auto_suggestions import build_stock_auto_mapping
from bling_app_zero.ui.mapping_confidence_state import current_confidence_from_widgets, ordered_targets_once, required_targets
from bling_app_zero.ui.mapping_constants import EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION
from bling_app_zero.ui.mapping_field_widget import render_mapping_select
from bling_app_zero.ui.mapping_filters import filter_targets
from bling_app_zero.ui.mapping_models import estoque_model, source_columns_from_df, target_columns_from_model
from bling_app_zero.ui.mapping_pagination import render_mapping_page_arrows, visible_targets
from bling_app_zero.ui.mapping_preview_builder import build_estoque_preview
from bling_app_zero.ui.mapping_sidebar_rule_badge import sidebar_rule_targets_from_columns
from bling_app_zero.ui.mapping_widget_state import clear_stale_mapping_widgets, is_manual_value, mapping_base

AUTO_MAPPING_LABEL = 'Ativar mapeamento automático'


def _auto_toggle_key(mapping_key: str) -> str:
    return f'{mapping_key}__auto_mapping_enabled'


def _auto_mode_key(mapping_key: str) -> str:
    return f'{mapping_key}__auto_mapping_mode'


def _blank_mapping(target_columns: list[str]) -> dict[str, str]:
    return {str(target): '' for target in target_columns}


def _clear_current_mapping_widgets(mapping_key: str) -> None:
    """Limpa apenas widgets dos campos, preservando o toggle de decisão do usuário."""
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(f'{mapping_key}_f') or text.startswith(f'{mapping_key}_manual_fixed_'):
            st.session_state.pop(key, None)


def _operation_signature() -> str:
    keys = (
        'bling_connected_api_operation',
        'flow_spine_sender_operation',
        'flow_spine_operation_resolved_for_api',
        'direct_bling_operation_applied',
        'active_feature_operation',
        'flow_spine_operation',
        'operacao_final',
        'operation',
        'selected_operation',
    )
    for key in keys:
        value = str(st.session_state.get(key) or '').strip().lower()
        if value:
            return value
    return 'estoque'


def _duplicated_source_columns(mapping: dict[str, str]) -> list[str]:
    used_values = [value for value in mapping.values() if value and not is_manual_value(value)]
    return sorted({value for value in used_values if value and used_values.count(value) > 1})


def _clear_stock_output() -> None:
    for key in (
        ESTOQUE_FINAL_KEY,
        ESTOQUE_MAPPING_KEY,
        ESTOQUE_CONFIDENCE_KEY,
        LEGACY_ESTOQUE_FINAL_KEY,
        LEGACY_ESTOQUE_MAPPING_KEY,
        LEGACY_ESTOQUE_CONFIDENCE_KEY,
    ):
        st.session_state.pop(key, None)


def _reset_stock_mapping(mapping_key: str, order_key: str, df_source: pd.DataFrame, model: pd.DataFrame) -> None:
    st.session_state[mapping_key] = build_stock_auto_mapping(df_source, model)
    _clear_stock_output()
    st.session_state.pop(order_key, None)
    st.session_state[_auto_mode_key(mapping_key)] = 'auto'
    _clear_current_mapping_widgets(mapping_key)
    pause_home_autofluxo_for_manual_review('gerar_estoque', reason='stock_mapping_reset_by_user')
    st.rerun()


def _render_auto_mapping_toggle(mapping_key: str) -> bool:
    enabled = st.toggle(
        AUTO_MAPPING_LABEL,
        value=False,
        key=_auto_toggle_key(mapping_key),
        help=(
            'Desligado: os campos de estoque começam vazios e você escolhe manualmente. '
            'Ligado: o sistema tenta sugerir as colunas automaticamente, mas você ainda precisa revisar.'
        ),
    )
    if enabled:
        st.caption('Mapeamento automático ligado: sugestões serão preenchidas para revisão do estoque.')
    else:
        st.caption('Mapeamento automático desligado: nenhuma coluna de estoque será ligada sem escolha manual do usuário.')
    return bool(enabled)


def _apply_mapping_mode_if_needed(
    mapping_key: str,
    order_key: str,
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    target_columns: list[str],
    auto_enabled: bool,
) -> None:
    desired_mode = 'auto' if auto_enabled else 'manual'
    current_mode = str(st.session_state.get(_auto_mode_key(mapping_key)) or '')
    if mapping_key in st.session_state and current_mode == desired_mode:
        return

    if auto_enabled:
        st.session_state[mapping_key] = build_stock_auto_mapping(df_source, model)
    else:
        st.session_state[mapping_key] = _blank_mapping(target_columns)
    st.session_state[_auto_mode_key(mapping_key)] = desired_mode
    st.session_state.pop(order_key, None)
    _clear_current_mapping_widgets(mapping_key)
    _clear_stock_output()


def render_manual_stock_mapping(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None, deposito: str = '') -> None:
    pause_home_autofluxo_for_manual_review('gerar_estoque', reason='stock_mapping_screen_visible')
    inject_mapping_css()

    model = estoque_model(df_modelo_estoque)
    source_columns = source_columns_from_df(df_source)
    target_columns = target_columns_from_model(model)
    sidebar_rule_targets = sidebar_rule_targets_from_columns(target_columns)
    options = [EMPTY_CHOOSE_OPTION, MANUAL_WRITE_OPTION, EMPTY_LEAVE_OPTION] + source_columns

    signature = df_signature(df_source) + ':' + _operation_signature() + ':' + str(deposito or '').strip() + ':' + '|'.join(target_columns)
    mapping_key = mapping_base('stk_map_', signature)
    order_key = f'{mapping_key}_order'

    clear_stale_mapping_widgets(mapping_key)

    st.markdown('##### Ligar colunas do estoque')
    st.caption(
        'Você decide se quer ligar as colunas de estoque manualmente ou ativar sugestões automáticas. '
        'Confira principalmente quantidade, balanço e depósito antes de continuar.'
    )
    with st.expander('Ver planilha enviada', expanded=False):
        preview_df('Planilha enviada', df_source)

    auto_enabled = _render_auto_mapping_toggle(mapping_key)
    _apply_mapping_mode_if_needed(mapping_key, order_key, df_source, model, target_columns, auto_enabled)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    current_confidence = current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = ordered_targets_once(order_key, target_columns, current_confidence)
    required = required_targets(target_columns)
    filtered_targets = filter_targets(mapping_key, ordered_targets, current_confidence, required, sidebar_rule_targets)
    render_mapping_fields_anchor()
    visible = visible_targets(mapping_key, filtered_targets)

    target_index_by_name = {target: index for index, target in enumerate(target_columns)}
    edited_mapping: dict[str, str] = {target: current_mapping.get(target, '') for target in target_columns}
    edited_confidence: dict[str, dict[str, object]] = current_confidence.copy()

    for target in visible:
        target_index = target_index_by_name.get(target, len(edited_mapping))
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

    if edited_mapping != current_mapping:
        pause_home_autofluxo_for_manual_review('gerar_estoque', reason='stock_mapping_changed_by_user')

    st.session_state[mapping_key] = edited_mapping
    df_preview_manual = build_estoque_preview(df_source, model, edited_mapping, target_columns, mapping_key)
    set_stock_output(df_preview_manual, edited_mapping, edited_confidence)

    duplicated = _duplicated_source_columns(edited_mapping)
    if duplicated:
        st.warning('A mesma coluna da origem foi usada mais de uma vez no estoque: ' + ', '.join(duplicated))

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar resultado', use_container_width=True, key=f'{mapping_key}_refresh'):
            pause_home_autofluxo_for_manual_review('gerar_estoque', reason='stock_mapping_refresh_by_user')
            st.rerun()
    with col_b:
        if st.button(
            'Tentar ligar colunas de novo',
            use_container_width=True,
            key=f'{mapping_key}_reset',
            disabled=not auto_enabled,
        ):
            _reset_stock_mapping(mapping_key, order_key, df_source, model)
    if not auto_enabled:
        st.caption('Para tentar ligar colunas automaticamente, ative primeiro o toggle “Ativar mapeamento automático”.')


def render_dual_stock_output(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None) -> None:
    st.markdown('#### Estoque')
    if not isinstance(df_modelo_estoque, pd.DataFrame) or not len(df_modelo_estoque.columns):
        st.info('Envie o modelo de estoque no passo inicial para gerar também a planilha de estoque.')
        return
    render_manual_stock_mapping(df_source, df_modelo_estoque, '')
    df_stock = stock_final_df()
    if isinstance(df_stock, pd.DataFrame) and not df_stock.empty:
        preview_df('Prévia do estoque', df_stock)
        download_final(df_stock, 'estoque')


__all__ = ['render_dual_stock_output', 'render_manual_stock_mapping']
