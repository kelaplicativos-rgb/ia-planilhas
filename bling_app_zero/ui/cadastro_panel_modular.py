from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.cadastro_mapping import render_dual_stock_output, render_manual_mapping
from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.cadastro_sources import (
    render_cadastro_source_upload,
    select_cadastro_model,
    select_estoque_model_for_cadastro,
)
from bling_app_zero.ui.home_shared import df_signature, download_final, preview_df, show_mapping

CADASTRO_SOURCE_SIGNATURE_KEY = 'cadastro_source_signature_atual'


def _source_dataframe(df_origem_site: pd.DataFrame | None, upload) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame):
        return df_origem_site
    source_df = getattr(upload, 'source_df', None)
    return source_df if isinstance(source_df, pd.DataFrame) else None


def _clear_cadastro_outputs_if_source_changed(df_origem: pd.DataFrame | None) -> None:
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return
    signature = df_signature(df_origem)
    previous = st.session_state.get(CADASTRO_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    for key in [
        'df_final_cadastro',
        'mapping_cadastro',
        'mapping_confidence_cadastro',
        'df_origem_cadastro_precificada',
        'df_final_estoque_from_cadastro',
        'mapping_estoque_from_cadastro',
        'mapping_confidence_estoque_from_cadastro',
    ]:
        st.session_state.pop(key, None)
    st.session_state[CADASTRO_SOURCE_SIGNATURE_KEY] = signature


def _render_final_cadastro_download() -> None:
    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        st.markdown('#### 🧾 Arquivo final de CADASTRO')
        st.caption('Baixe aqui somente o CSV de cadastro de produtos.')
        show_mapping(mapping, operation='cadastro')
        preview_df('🧾 CADASTRO · Preview final', df_final)
        download_final(df_final, 'cadastro', 'cadastro')


def render_cadastro_panel() -> None:
    df_origem_site = get_site_source_for_operation('cadastro')
    upload = render_cadastro_source_upload(df_origem_site)
    df_origem = _source_dataframe(df_origem_site, upload)
    _clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        if isinstance(df_modelo, pd.DataFrame) and isinstance(df_modelo_estoque, pd.DataFrame):
            st.success('Cadastro e estoque detectados. O sistema vai gerar os dois arquivos.')

        df_para_mapear = render_cadastro_pricing(df_origem)
        df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
        render_manual_mapping(df_para_mapear, df_modelo)
        render_dual_stock_output(df_para_mapear, df_modelo_estoque)
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.session_state.pop('df_final_cadastro', None)
        st.session_state.pop('mapping_cadastro', None)

    _render_final_cadastro_download()
