from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_autofluxo import pause_home_autofluxo_for_manual_review
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
    pause_home_autofluxo_for_manual_review('mapeamento', reason='cadastro_mapping_reset_by_user')
    st.rerun()


def _render_cadastro_actions(
    mapping_key: str,
    order_key: str,
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    source_columns: list[str],
) -> None:
    with st.expander('Outras ações', expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button('Atualizar prévia', use_container_width=True, key=f'{mapping_key}_refresh'):
                pause_home_autofluxo_for_manual_review('mapeamento', reason='cadastro_mapping_refresh_by_user')
                st.rerun()
        with col_b:
            if st.button('Refazer sugestões', use_container_width=True, key=f'{mapping_key}_reset'):
                _reset_cadastro_mapping(mapping_key, order_key, df_source, model, source_columns)


def _render_compact_mapping_header(df_source: pd.DataFrame) -> None:
    st.markdown('### Mapear campos')
    st.caption(f'{len(df_source)} produto(s) carregado(s). Confira as ligações abaixo.')
    st.info('Escolha a coluna correta para cada campo do Bling. Depois confirme o mapeamento.')
    with st.expander('Ver dados de origem', expanded=False):
        preview_df('Origem', df_source)


def render_manual_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    pause_home_autofluxo_for_manual_review('mapeamento', reason='cadastro_mapping_screen_visible')
    inject_mapping_css()

    model = cadastro_model(df_modelo)
    source_columns = source_columns_from_df(df_source)
    target_columns = target_columns_from_model(model)
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

    _render_compact_mapping_header(df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    with st.expander('Ajuda da IA', expanded=False):
        render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Analisar campos pendentes')

    current_confidence = current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = ordered_targets_once(order_key, target_columns, current_confidence)
    required = required_targets(target_columns)
    filtered_targets = filter_targets(mapping_key, ordered_targets, current_confidence, required)
    visible = visible_targets(mapping_key, filtered_targets)

    render_mapping_page_arrows(mapping_key, position='top')

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

    render_mapping_page_arrows(mapping_key, position='bottom')

    if edited_mapping != current_mapping:
        pause_home_autofluxo_for_manual_review('mapeamento', reason='cadastro_mapping_changed_by_user')
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)

    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_cadastro'] = edited_confidence

    df_preview_manual = build_cadastro_preview(df_source, model, edited_mapping, target_columns, mapping_key)
    st.session_state['df_final_cadastro'] = df_preview_manual
    st.session_state['mapping_cadastro'] = edited_mapping

    duplicated = _duplicated_source_columns(edited_mapping)
    if duplicated:
        st.warning('Coluna repetida: ' + ', '.join(duplicated))

    render_confirm_mapping_button(edited_mapping, df_preview_manual, mapping_key, target_columns)
    _render_cadastro_actions(mapping_key, order_key, df_source, model, source_columns)


__all__ = ['render_manual_mapping']