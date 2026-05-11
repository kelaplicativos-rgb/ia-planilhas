from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import super_auto_map_columns
from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.home_shared import df_signature, preview_df
from bling_app_zero.ui.layout import inject_mapping_css, render_mapping_preview, render_mapping_title

EMPTY_LEAVE_OPTION = '— deixar vazio —'
MANUAL_WRITE_OPTION = '— escrever valor fixo —'
MANUAL_MAPPING_VALUE = '__BLING_MANUAL_FIXED_VALUE__'
STOCK_MAPPING_PREFIX = 'estoque_map_'


def _short_hash(value: str, size: int = 12) -> str:
    return hashlib.sha1(str(value or '').encode('utf-8', errors='ignore')).hexdigest()[:size]


def _mapping_base(signature: str) -> str:
    return f'{STOCK_MAPPING_PREFIX}{_short_hash(signature)}'


def _target_widget_key(mapping_key: str, target_index: int) -> str:
    return f'{mapping_key}_f{target_index:03d}'


def _manual_value_key(widget_key: str) -> str:
    return f'{widget_key}__manual_value'


def _is_manual_value(value: str | None) -> bool:
    return str(value or '').strip() == MANUAL_MAPPING_VALUE


def _option_value(value: str | None) -> str:
    text = str(value or '').strip()
    if text in {EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION, MANUAL_MAPPING_VALUE}:
        return ''
    return text


def _default_index(options: list[str], current_value: str) -> int:
    display_value = MANUAL_WRITE_OPTION if _is_manual_value(current_value) else current_value or EMPTY_LEAVE_OPTION
    try:
        return options.index(display_value)
    except ValueError:
        return 0


def _first_row_preview(df_source: pd.DataFrame, selected_column: str) -> str:
    selected_column = _option_value(selected_column)
    if not selected_column or selected_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    return text[:160] + ('...' if len(text) > 160 else '')


def _clear_old_stock_widgets(active_mapping_key: str) -> None:
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(STOCK_MAPPING_PREFIX) and not text.startswith(active_mapping_key):
            st.session_state.pop(text, None)


def _manual_fixed_values(df: pd.DataFrame, mapping: dict[str, str], target_columns: list[str], mapping_key: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for index, target in enumerate(target_columns):
        if not _is_manual_value(mapping.get(target, '')) or target not in out.columns:
            continue
        widget_key = _target_widget_key(mapping_key, index)
        out[target] = str(st.session_state.get(_manual_value_key(widget_key), '') or '')
    return out


def _fill_deposito(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in out.columns:
        if 'deposito' in normalize_key(column):
            out[column] = deposito
    return out


def _enforce_model_columns(df: pd.DataFrame, model: pd.DataFrame) -> pd.DataFrame:
    return df.reindex(columns=list(model.columns), fill_value='')


def _render_target_mapping(
    df_source: pd.DataFrame,
    target: str,
    target_index: int,
    current_value: str,
    mapping_key: str,
    options: list[str],
    deposito: str,
) -> str:
    widget_key = _target_widget_key(mapping_key, target_index)
    target_key = normalize_key(target)

    with st.container(border=True):
        if 'deposito' in target_key:
            render_mapping_title(f'🟢 {target}')
            st.text_input(target, value=deposito, disabled=True, key=f'{widget_key}_deposito', label_visibility='collapsed')
            st.caption('Depósito preenchido pelo campo informado na entrada do estoque.')
            return ''

        render_mapping_title(f'🟡 {target}')
        selected_raw = st.selectbox(
            target,
            options,
            index=_default_index(options, current_value),
            key=widget_key,
            label_visibility='collapsed',
        )
        if selected_raw == MANUAL_WRITE_OPTION:
            manual_value = st.text_input(
                f'Valor fixo para {target}',
                value=str(st.session_state.get(_manual_value_key(widget_key), '') or ''),
                key=_manual_value_key(widget_key),
                placeholder='Digite o valor que será repetido nesta coluna',
            )
            st.caption('Valor fixo aplicado em todas as linhas desta coluna.')
            _ = manual_value
            return MANUAL_MAPPING_VALUE
        if selected_raw == EMPTY_LEAVE_OPTION:
            st.caption('Esta coluna ficará vazia no CSV final.')
            return ''
        render_mapping_preview(_first_row_preview(df_source, selected_raw))
        return _option_value(selected_raw)


def render_manual_estoque_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    """Mapeamento manual exclusivo do fluxo de estoque.

    Não depende do módulo de cadastro. Mantém as colunas exatamente na ordem do
    modelo de estoque anexado e não cria dados sem escolha do usuário.
    """
    inject_mapping_css()
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        st.warning('Origem de estoque vazia.')
        return
    if not isinstance(df_modelo, pd.DataFrame) or not len(df_modelo.columns):
        st.warning('Modelo de estoque ausente.')
        return

    model = df_modelo.copy().fillna('')
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns) + f':{deposito}'
    mapping_key = _mapping_base(signature)
    _clear_old_stock_widgets(mapping_key)

    if mapping_key not in st.session_state:
        auto_mapping = super_auto_map_columns(df_source, model)
        for target in target_columns:
            if 'deposito' in normalize_key(target):
                auto_mapping[target] = ''
        st.session_state[mapping_key] = {target: str(auto_mapping.get(target, '') or '') for target in target_columns}

    st.markdown('#### Conferir campos do estoque')
    st.caption('Cada coluna do modelo anexado precisa ser conferida. O que não existir deve ficar vazio.')
    with st.expander('Ver origem antes de mapear', expanded=False):
        preview_df('Origem do estoque', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    edited_mapping: dict[str, str] = {target: current_mapping.get(target, '') for target in target_columns}

    for index, target in enumerate(target_columns):
        edited_mapping[target] = _render_target_mapping(
            df_source,
            target,
            index,
            current_mapping.get(target, ''),
            mapping_key,
            options,
            deposito,
        )

    st.session_state[mapping_key] = edited_mapping
    mapping_for_apply = {target: value for target, value in edited_mapping.items() if not _is_manual_value(value)}
    df_final = apply_mapping(df_source, model, mapping_for_apply)
    df_final = _manual_fixed_values(df_final, edited_mapping, target_columns, mapping_key)
    df_final = _fill_deposito(df_final, deposito)
    df_final = _enforce_model_columns(df_final, model)
    df_final = sanitize_for_bling(df_final)
    df_final = _enforce_model_columns(df_final, model)

    st.session_state['df_final_estoque_from_cadastro'] = df_final
    st.session_state['mapping_estoque_from_cadastro'] = edited_mapping
    st.session_state['mapping_confidence_estoque_from_cadastro'] = {}

    used_values = [value for value in edited_mapping.values() if value and not _is_manual_value(value)]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna da origem foi usada em mais de um campo: ' + ', '.join(duplicated))

    if st.button('Atualizar prévia do estoque', use_container_width=True, key=f'{mapping_key}_refresh'):
        st.rerun()
