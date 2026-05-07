from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.pricing import detect_discount_percent
from bling_app_zero.ui.home_shared import (
    df_signature,
    download_final,
    load_apply_pricing,
    load_cadastro_pipeline,
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

        if st.button('Gerar cadastro Bling', use_container_width=True):
            run_cadastro_pipeline = load_cadastro_pipeline()
            df_para_gerar = st.session_state.get('df_origem_cadastro_precificada', df_origem)
            df_final, mapping = run_cadastro_pipeline(df_para_gerar, df_modelo)
            st.session_state['df_final_cadastro'] = df_final
            st.session_state['mapping_cadastro'] = mapping
    elif upload.attachments:
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem tabular válida para o cadastro.')

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do cadastro', df_final)
        download_final(df_final, 'cadastro', 'cadastro')
