from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_estoque_model, get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def select_cadastro_model(upload) -> pd.DataFrame | None:
    site_model = get_site_model_for_operation('cadastro')
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        save_home_models(upload.cadastro_model_df, upload.estoque_model_df)
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        save_home_models(upload.model_df, upload.estoque_model_df)
        return upload.model_df
    return None


def select_estoque_model_for_cadastro(upload) -> pd.DataFrame | None:
    site_model = get_site_estoque_model()
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else upload.model_df
        save_home_models(cadastro_model, upload.estoque_model_df)
        return upload.estoque_model_df
    return None


def render_cadastro_source_upload(df_origem_site: pd.DataFrame | None):
    home_has_models = get_home_cadastro_model() is not None or get_home_estoque_model() is not None
    allow_model_upload = not home_has_models
    if isinstance(df_origem_site, pd.DataFrame):
        st.success('Origem criada pelo site carregada com sucesso.')
        st.caption('Agora confira, precifique se quiser e gere o CSV final de cadastro.')
        return render_smart_upload_box(
            title='Arquivo complementar do fornecedor',
            operation='cadastro',
            key='smart_upload_cadastro',
            allow_model=allow_model_upload,
            required_model=False,
            accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
        )

    st.markdown('### Origem dos produtos')
    st.caption('Envie a planilha, PDF ou XML do fornecedor. O sistema transforma essa origem no padrão do Bling.')
    if home_has_models:
        st.success('Modelo do Bling já carregado. Envie somente o arquivo do fornecedor.')
    return render_smart_upload_box(
        title='Arquivo do fornecedor',
        operation='cadastro',
        key='smart_upload_cadastro',
        allow_model=allow_model_upload,
        required_model=False,
        accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
    )
