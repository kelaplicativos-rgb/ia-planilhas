from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import df_signature, preview_df
from bling_app_zero.ui.layout import inject_mapping_css
from bling_app_zero.ui.mapping_ai_actions import render_ai_button
from bling_app_zero.ui.mapping_auto_suggestions import build_super_mapping
from bling_app_zero.ui.mapping_confirmation import render_confirm_mapping_button
from bling_app_zero.ui.mapping_confidence_state import current_confidence_from_widgets, ordered_targets_once, required_targets
from bling_app_zero.ui.mapping_constants import (
    CADASTRO_MAPPING_CONFIRMED_KEY,
    CADASTRO_MAPPING_SIGNATURE_KEY,
    EMPTY_CHOOSE_OPTION,
    EMPTY_LEAVE_OPTION,
    MANUAL_WRITE_OPTION,
)
from bling_app_zero.ui.mapping_field_widget import render_mapping_select
from bling_app_zero.ui.mapping_filters import filter_targets
from bling_app_zero.ui.mapping_models import cadastro_model, source_columns_from_df, target_columns_from_model
from bling_app_zero.ui.mapping_pagination import render_mapping_page_arrows, visible_targets
from bling_app_zero.ui.mapping_preview_builder import build_cadastro_preview
from bling_app_zero.ui.mapping_sidebar_rule_badge import sidebar_rule_targets_from_columns
from bling_app_zero.ui.mapping_widget_state import clear_mapping_widgets, clear_stale_mapping_widgets, is_manual_value, mapping_base


def _duplicated_source_columns(mapping: dict[str, str]) -> list[str]:
    used_values = [value for value in mapping.values() if value and not is_manual_value(value)]
    return sorted({value for value in used_values if used_values.count(value) > 1})


def _reset_cadastro_mapping(
    mapping_key: str,
    order_key: str,
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    source_columns: list[str],
) -> None:
    st.session_state[mapping_key] = build_super_mapping(df_source, model, source_columns)
    st.session_state.pop('df_final_cadastro', None)
    st.session_state.pop('mapping_cadastro', None)
    st.session_state.pop('mapping_confidence_cadastro', None)
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    st.session_state.pop(order_key, None)
    clear_mapping_widgets(mapping_key)
    st.rerun()


def _render_cadastro_actions(
    mapping_key: str,
    order_key: str,
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    source_columns: list[str],
) -> None:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar prévia do cadastro', use_container_width=True, key=f'{mapping_key}_refresh'):
            st.rerun()
    with col_b:
        if st.button('Refazer sugestões automáticas', use_container_width=True, key=f'{mapping_key}_reset'):
            _reset_cadastro_mapping(mapping_key, order_key, df_source, model, source_columns)


def render_manual_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    inject_mapping_css()

    model = cadastro_model(df_modelo)
    source_columns = source_columns_from_df(df_source)
    target_columns = target_columns_from_model(model)
    sidebar_rule_targets = sidebar_rule_targets_from_columns(target_columns)
    options = [EMPTY_CHOOSE_OPTION, MANUAL_WRITE_OPTION, EMPTY_LEAVE_OPTION] + source_columns

    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    mapping_key = mapping_base('cad_map_', signature)
    order_key = f'{mapping_key}_order'

    clear_stale_mapping_widgets(mapping_key)
    if mapping_key not in st.session_state:
        st.session_state[mapping_key] = build_super_mapping(df_source, model, source_columns)
        st.session_state.pop(order_key, None)
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)

    st.markdown('#### 2. Conferir campos do cadastro')
    st.caption('🔴 precisa escolher · 🟡 sugestão para conferir · 🟢 sugestão forte/valor confirmado · 🟣 regra/recurso do fluxo')
    with st.expander('Ver origem antes de preencher', expanded=False):
        preview_df('Origem para conferir', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Pedir ajuda da IA nos campos em dúvida')

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
    st.session_state['mapping_confidence_cadastro'] = edited_confidence

    df_preview_manual = build_cadastro_preview(df_source, model, edited_mapping, target_columns, mapping_key)
    st.session_state['df_final_cadastro'] = df_preview_manual
    st.session_state['mapping_cadastro'] = edited_mapping

    duplicated = _duplicated_source_columns(edited_mapping)
    if duplicated:
        st.warning('A mesma coluna da origem foi usada em mais de um campo: ' + ', '.join(duplicated))

    render_confirm_mapping_button(edited_mapping, df_preview_manual, mapping_key, target_columns)
    _render_cadastro_actions(mapping_key, order_key, df_source, model, source_columns)


__all__ = ['render_manual_mapping']
