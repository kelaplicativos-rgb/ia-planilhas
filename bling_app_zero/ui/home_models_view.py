from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_models_state import (
    WIZARD_STEP_KEY,
    clear_default_home_models,
    df_log_summary,
    get_home_cadastro_model,
    get_home_estoque_model,
    save_home_models,
)
from bling_app_zero.ui.home_models_upload import auto_forward_after_first_model_upload, remember_original_model_upload
from bling_app_zero.ui.model_upload import render_model_upload_box

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models_view.py'


def _model_summary_df() -> pd.DataFrame | None:
    cadastro = get_home_cadastro_model()
    estoque = get_home_estoque_model()
    if isinstance(cadastro, pd.DataFrame):
        return cadastro
    if isinstance(estoque, pd.DataFrame):
        return estoque
    return None


def _render_loaded_summary() -> None:
    df = _model_summary_df()
    if not isinstance(df, pd.DataFrame):
        st.warning(
            'Envie o modelo final de destino para continuar. '
            'Use uma planilha com cabeçalho na primeira linha e com as colunas finais que o sistema deverá preencher.'
        )
        return
    st.caption(f'Modelo de destino enviado · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo de destino', expanded=False):
        columns = [str(column) for column in list(df.columns)]
        st.caption(', '.join(columns))


def _render_model_type_guidance() -> None:
    st.markdown('#### Bling')
    st.caption(
        'Configure aqui a estrutura final da planilha. Esta etapa não faz parte da calculadora de preço.'
    )

    col_bling, col_universal = st.columns(2)
    with col_bling:
        with st.container(border=True):
            st.markdown('##### Modelos Bling')
            st.caption(
                'Para modelos oficiais do Bling, como cadastro de produtos, estoque ou atualização de preços.'
            )
    with col_universal:
        with st.container(border=True):
            st.markdown('##### Modelos Universal')
            st.caption(
                'Para marketplace, fornecedor ou qualquer layout final com cabeçalho próprio.'
            )


def render_home_bling_models() -> None:
    # Nome legado mantido por compatibilidade. Visualmente esta tela representa a central Bling/Universal.
    clear_default_home_models()
    _render_model_type_guidance()

    st.markdown('#### Modelo de destino')
    st.caption(
        'Anexe abaixo o modelo que será preenchido no final. '
        'Pode ser modelo Bling ou modelo universal com cabeçalho próprio.'
    )

    upload = render_model_upload_box(
        title='Enviar modelo final de destino',
        operation='universal',
        key='home_model_upload_bling',
        required_model=False,
        caption=None,
    )
    cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else None
    estoque_model = upload.estoque_model_df if isinstance(upload.estoque_model_df, pd.DataFrame) else None

    if isinstance(cadastro_model, pd.DataFrame) or isinstance(estoque_model, pd.DataFrame):
        remember_original_model_upload(upload)
        add_audit_event(
            'home_universal_model_upload_ready_to_save',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='OK',
            details={
                'cadastro': df_log_summary(cadastro_model),
                'estoque': df_log_summary(estoque_model),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        save_home_models(cadastro_model, estoque_model, replace_missing=True)
        auto_forward_after_first_model_upload(cadastro_model, estoque_model)

    _render_loaded_summary()


__all__ = ['render_home_bling_models']
