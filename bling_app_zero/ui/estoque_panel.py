from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import (
    download_final,
    load_estoque_pipeline,
    preview_df,
    show_contract,
    show_mapping,
)
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def render_estoque_panel() -> None:
    st.warning('Motor independente de ESTOQUE será carregado somente quando gerar.')
    st.caption('Este fluxo usa somente as colunas pedidas pelo modelo de estoque. Se não encontrar um campo, ele fica vazio.')

    upload = render_smart_upload_box(
        title='📎 Anexos do estoque',
        operation='estoque',
        key='smart_upload_estoque',
        allow_model=True,
        required_model=True,
        accepted_types=['xlsx', 'xls', 'csv'],
    )

    df_origem = upload.source_df
    df_modelo = upload.model_df

    if isinstance(df_modelo, pd.DataFrame):
        show_contract([str(c) for c in df_modelo.columns])

    deposito = st.text_input('Nome do depósito', value='Não definido')

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        if st.button('Gerar atualização de estoque', use_container_width=True):
            run_estoque_pipeline = load_estoque_pipeline()
            df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
            st.session_state['df_final_estoque'] = df_final
            st.session_state['mapping_estoque'] = mapping
    elif upload.attachments:
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem tabular válida para o estoque.')

    df_final = st.session_state.get('df_final_estoque')
    mapping = st.session_state.get('mapping_estoque', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do estoque', df_final)
        download_final(df_final, 'estoque', 'estoque')
