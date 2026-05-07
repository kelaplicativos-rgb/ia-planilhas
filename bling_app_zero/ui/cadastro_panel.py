from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import (
    download_final,
    load_apply_pricing,
    load_cadastro_pipeline,
    preview_df,
    read_upload_fast,
    show_mapping,
)


def render_cadastro_panel() -> None:
    st.success('Motor independente de CADASTRO será carregado somente quando gerar.')

    col_a, col_b = st.columns(2)
    with col_a:
        origem = st.file_uploader(
            'Origem dos produtos: planilha, XML ou PDF',
            type=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
            key='upload_cadastro',
        )
    with col_b:
        modelo = st.file_uploader(
            'Modelo de cadastro do Bling (opcional)',
            type=['xlsx', 'xls', 'csv'],
            key='modelo_cadastro',
        )

    usar_preco = st.checkbox('Aplicar calculadora de preço antes do mapeamento', value=False)

    if origem:
        df_origem = read_upload_fast(origem)
        preview_df('Preview da origem', df_origem)

        if usar_preco and df_origem is not None and not df_origem.empty:
            apply_pricing = load_apply_pricing()
            colunas = [str(c) for c in df_origem.columns]
            coluna_custo = st.selectbox('Coluna de custo/preço base', colunas)
            c1, c2, c3, c4 = st.columns(4)
            margem = c1.number_input('Lucro %', min_value=0.0, value=30.0, step=1.0)
            imposto = c2.number_input('Impostos %', min_value=0.0, value=0.0, step=1.0)
            taxa = c3.number_input('Taxas %', min_value=0.0, value=0.0, step=1.0)
            fixo = c4.number_input('Custo fixo R$', min_value=0.0, value=0.0, step=1.0)
            df_origem = apply_pricing(df_origem, coluna_custo, 'Preço de venda', margem, imposto, taxa, fixo)
            preview_df('Origem com preço calculado', df_origem)

        if st.button('Gerar cadastro Bling', use_container_width=True):
            run_cadastro_pipeline = load_cadastro_pipeline()
            df_modelo = read_upload_fast(modelo) if modelo else None
            df_final, mapping = run_cadastro_pipeline(df_origem, df_modelo)
            st.session_state['df_final_cadastro'] = df_final
            st.session_state['mapping_cadastro'] = mapping

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do cadastro', df_final)
        download_final(df_final, 'cadastro', 'cadastro')
