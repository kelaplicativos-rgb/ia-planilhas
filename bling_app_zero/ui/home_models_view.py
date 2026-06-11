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
    get_home_preco_model,
    get_home_universal_model,
    save_home_models,
)
from bling_app_zero.ui.home_models_upload import auto_forward_after_first_model_upload, remember_original_model_upload
from bling_app_zero.ui.model_upload import render_model_upload_box

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models_view.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
MODEL_LABEL = 'Modelo para mapear'
UPLOAD_LABEL = 'Enviar modelo para mapear'


def _entry_context() -> str:
    return str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()


def _model_summary_df() -> pd.DataFrame | None:
    for df in (get_home_universal_model(), get_home_cadastro_model(), get_home_estoque_model(), get_home_preco_model()):
        if isinstance(df, pd.DataFrame):
            return df
    return None


def _render_loaded_summary() -> None:
    df = _model_summary_df()
    if not isinstance(df, pd.DataFrame):
        st.warning('Envie o modelo para mapear. Use uma planilha com as colunas finais que o sistema deverá preencher.')
        return
    st.caption(f'{MODEL_LABEL} carregado · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo para mapear', expanded=False):
        columns = [str(column) for column in list(df.columns)]
        st.caption(', '.join(columns))


def _render_model_type_guidance() -> None:
    st.markdown(f'#### {MODEL_LABEL}')
    st.caption('Anexe qualquer planilha modelo. Ela será usada como layout final para o mapeamento e para o download.')
    with st.container(border=True):
        st.markdown('##### Layout universal')
        st.caption('Use para marketplace, fornecedor, sistema próprio ou qualquer outro modelo de planilha.')


def _split_models_by_contract(upload) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    df = upload.model_df if isinstance(upload.model_df, pd.DataFrame) else None
    if not isinstance(df, pd.DataFrame):
        return None, None, None, None
    st.session_state['destination_model_contract_type'] = 'universal'
    st.session_state['destination_model_contract_label'] = MODEL_LABEL
    st.session_state['destination_model_contract_confidence'] = 1.0
    st.session_state['destination_model_contract_reason'] = 'Modelo universal para mapear.'
    # O mesmo modelo é salvo em todos os slots para não travar fluxos antigos
    # que ainda procuram cadastro/estoque/preço, mas sem fazer classificação.
    return df, df, df, df


def render_home_bling_models() -> None:
    clear_default_home_models()
    _render_model_type_guidance()

    st.markdown(f'#### {UPLOAD_LABEL}')
    st.caption('Anexe o modelo que será preenchido no final. Não há reconhecimento por tipo: o layout enviado é o contrato da saída.')

    upload = render_model_upload_box(
        title=UPLOAD_LABEL,
        operation='universal',
        key='home_model_upload_bling',
        required_model=False,
        caption=None,
    )
    cadastro_model, estoque_model, preco_model, universal_model = _split_models_by_contract(upload)

    if any(isinstance(df, pd.DataFrame) for df in (cadastro_model, estoque_model, preco_model, universal_model)):
        remember_original_model_upload(upload)
        add_audit_event(
            'home_universal_mapping_model_upload_ready_to_save',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='OK',
            details={
                'entry_context': _entry_context(),
                'contract_type': 'universal',
                'contract_label': MODEL_LABEL,
                'cadastro': df_log_summary(cadastro_model),
                'estoque': df_log_summary(estoque_model),
                'preco': df_log_summary(preco_model),
                'universal': df_log_summary(universal_model),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        save_home_models(cadastro_model, estoque_model, preco_model, universal_model, replace_missing=True)
        auto_forward_after_first_model_upload(cadastro_model, estoque_model)

    _render_loaded_summary()


__all__ = ['render_home_bling_models']
