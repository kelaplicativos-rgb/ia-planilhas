from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import (
    download_final,
    load_estoque_pipeline,
    preview_df,
    read_upload_fast,
    show_contract,
    show_mapping,
)


def render_estoque_panel() -> None:
    st.warning('Motor independente de ESTOQUE será carregado somente quando gerar.')
    st.caption('Este fluxo usa somente as colunas pedidas pelo modelo de estoque. Se não encontrar um campo, ele fica vazio.')

    col_a, col_b = st.columns(2)
    with col_a:
        origem = st.file_uploader(
            'Origem dos dados de estoque',
            type=['xlsx', 'xls', 'csv'],
            key='upload_estoque_origem',
        )
    with col_b:
        modelo = st.file_uploader(
            'Modelo de estoque do Bling',
            type=['xlsx', 'xls', 'csv'],
            key='modelo_estoque',
        )

    deposito = st.text_input('Nome do depósito', value='Não definido')

    if modelo:
        df_modelo_preview = read_upload_fast(modelo)
        if isinstance(df_modelo_preview, pd.DataFrame):
            show_contract([str(c) for c in df_modelo_preview.columns])

    if origem:
        df_origem = read_upload_fast(origem)
        df_modelo = read_upload_fast(modelo) if modelo else None
        preview_df('Preview da origem de estoque', df_origem)

        if st.button('Gerar atualização de estoque', use_container_width=True):
            run_estoque_pipeline = load_estoque_pipeline()
            df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
            st.session_state['df_final_estoque'] = df_final
            st.session_state['mapping_estoque'] = mapping

    df_final = st.session_state.get('df_final_estoque')
    mapping = st.session_state.get('mapping_estoque', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do estoque', df_final)
        download_final(df_final, 'estoque', 'estoque')
