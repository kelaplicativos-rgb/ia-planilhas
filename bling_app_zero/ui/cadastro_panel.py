from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping, auto_map_columns
from bling_app_zero.core.pricing import detect_discount_percent
from bling_app_zero.engines.cadastro_engine import default_model
from bling_app_zero.ui.home_shared import (
    df_signature,
    download_final,
    load_apply_pricing,
    preview_df,
    show_mapping,
)
from bling_app_zero.ui.smart_upload import render_smart_upload_box

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]


def _apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df

    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in PRICE_TARGET_ALIASES:
        out[column] = calculated_values
    return out


def _best_cost_column(columns: list[str]) -> int:
    preferred_terms = ['custo', 'preço custo', 'preco custo', 'valor produto', 'valor', 'preço', 'preco', 'price']
    lower_columns = [column.lower() for column in columns]
    for term in preferred_terms:
        for index, column in enumerate(lower_columns):
            if term in column:
                return index
    return 0


def _sync_detected_discount(df_origem: pd.DataFrame, signature: str) -> float:
    detected = float(detect_discount_percent(df_origem) or 0.0)
    previous_signature = st.session_state.get('cadastro_precificacao_signature')

    if previous_signature != signature:
        st.session_state['cadastro_precificacao_signature'] = signature
        st.session_state['cadastro_desconto_comissao'] = detected

    if 'cadastro_desconto_comissao' not in st.session_state:
        st.session_state['cadastro_desconto_comissao'] = detected

    return detected


def _cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return default_model()


def _default_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def _first_row_preview(df_source: pd.DataFrame, selected_column: str) -> str:
    if not selected_column or selected_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    if len(text) > 180:
        text = text[:180] + '...'
    return text


def _show_first_row_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    text = _first_row_preview(df_source, selected_column)
    if not text:
        return
    safe_text = html.escape(text)
    st.markdown(
        f"<div style='font-size:14px; color:#118a32; margin-top:-8px; margin-bottom:12px; font-weight:700;'>"
        f"{safe_text}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_manual_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    model = _cadastro_model(df_modelo)
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [''] + source_columns

    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    mapping_key = f'cadastro_manual_mapping_{signature}'

    if mapping_key not in st.session_state:
        st.session_state[mapping_key] = auto_map_columns(df_source, model)

    st.markdown('#### 2. Correlacionar colunas')
    st.caption('Confira as sugestões e ajuste manualmente antes de gerar o preview final.')

    with st.expander('Prévia da origem usada no mapeamento', expanded=False):
        preview_df('Origem para correlacionar', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    edited_mapping: dict[str, str] = {}

    for target in target_columns:
        suggested = current_mapping.get(target, '')
        if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
            suggested = 'Preço de venda'

        selected = st.selectbox(
            target,
            options,
            index=_default_index(options, suggested),
            key=f'{mapping_key}_{target}',
            help=f'Campo de destino no Bling: {target}',
        )
        _show_first_row_preview(df_source, selected)
        edited_mapping[target] = selected

    st.session_state[mapping_key] = edited_mapping

    used_values = [value for value in edited_mapping.values() if value]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('Atenção: a mesma coluna de origem foi usada mais de uma vez: ' + ', '.join(duplicated))

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Gerar preview final do cadastro', use_container_width=True):
            df_final = apply_mapping(df_source, model, edited_mapping)
            st.session_state['df_final_cadastro'] = sanitize_for_bling(df_final)
            st.session_state['mapping_cadastro'] = edited_mapping
    with col_b:
        if st.button('Limpar correlação deste cadastro', use_container_width=True):
            st.session_state.pop(mapping_key, None)
            st.session_state.pop('df_final_cadastro', None)
            st.session_state.pop('mapping_cadastro', None)
            st.rerun()


def render_cadastro_panel() -> None:
    st.success('Motor independente de CADASTRO será carregado somente quando gerar.')

    upload = render_smart_upload_box(
        title='📎 Anexos do cadastro',
        operation='cadastro',
        key='smart_upload_cadastro',
        allow_model=True,
        required_model=False,
        accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
    )

    df_origem = upload.source_df
    df_modelo = upload.model_df

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        usar_preco = st.checkbox('Aplicar calculadora de preço antes do mapeamento', value=False)

        if usar_preco:
            apply_pricing = load_apply_pricing()
            colunas = [str(c) for c in df_origem.columns]
            origem_signature = df_signature(df_origem)
            desconto_detectado = _sync_detected_discount(df_origem, origem_signature)

            coluna_custo = st.selectbox(
                'Coluna de custo/preço base',
                colunas,
                index=_best_cost_column(colunas),
                key=f'cadastro_coluna_custo_{origem_signature}',
            )
            _show_first_row_preview(df_origem, coluna_custo)

            if desconto_detectado > 0:
                st.info(f'Desconto/comissão detectado e aplicado como padrão: {desconto_detectado:.2f}%')

            c1, c2, c3, c4, c5 = st.columns(5)
            margem = c1.number_input(
                'Lucro desejado %',
                min_value=0.0,
                value=30.0,
                step=1.0,
                key=f'cadastro_margem_{origem_signature}',
            )
            imposto = c2.number_input(
                'Impostos %',
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f'cadastro_imposto_{origem_signature}',
            )
            taxa = c3.number_input(
                'Taxas %',
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f'cadastro_taxa_{origem_signature}',
            )
            desconto = c4.number_input(
                'Desconto/Comissão %',
                min_value=0.0,
                step=1.0,
                key='cadastro_desconto_comissao',
            )
            fixo = c5.number_input(
                'Custo fixo R$',
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f'cadastro_fixo_{origem_signature}',
            )

            df_origem = apply_pricing(
                df_origem,
                coluna_custo,
                'Preço de venda',
                margem,
                imposto,
                taxa,
                fixo,
                desconto,
            )
            df_origem = _apply_calculated_price_aliases(df_origem, 'Preço de venda')
            st.session_state['cadastro_preco_calculado_ativo'] = True
            st.session_state['df_origem_cadastro_precificada'] = df_origem
            preview_df('Origem com preço calculado', df_origem)
        else:
            st.session_state['cadastro_preco_calculado_ativo'] = False
            st.session_state.pop('df_origem_cadastro_precificada', None)

        df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_origem)
        _render_manual_mapping(df_para_mapear, df_modelo)
    elif upload.attachments:
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem tabular válida para o cadastro.')

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do cadastro', df_final)
        download_final(df_final, 'cadastro', 'cadastro')
