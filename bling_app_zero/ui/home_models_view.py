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
from bling_app_zero.universal.model_contract_detector import CONTRACT_LABELS, MODEL_CONTRACT_TYPE_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models_view.py'


def _model_summary_df() -> pd.DataFrame | None:
    for df in (get_home_cadastro_model(), get_home_estoque_model(), get_home_preco_model(), get_home_universal_model()):
        if isinstance(df, pd.DataFrame):
            return df
    return None


def _first_valid_df(*items: pd.DataFrame | None) -> pd.DataFrame | None:
    for df in items:
        if isinstance(df, pd.DataFrame):
            return df
    return None


def _render_loaded_summary() -> None:
    df = _model_summary_df()
    if not isinstance(df, pd.DataFrame):
        st.warning(
            'Envie o modelo final de destino para continuar. '
            'Use uma planilha com cabeçalho na primeira linha e com as colunas finais que o sistema deverá preencher.'
        )
        return
    contract_type = str(st.session_state.get(MODEL_CONTRACT_TYPE_KEY) or 'universal')
    label = CONTRACT_LABELS.get(contract_type, CONTRACT_LABELS['universal'])
    st.caption(f'{label} carregado · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo de destino', expanded=False):
        columns = [str(column) for column in list(df.columns)]
        st.caption(', '.join(columns))


def _render_model_type_guidance() -> None:
    st.markdown('#### Bling')
    st.caption('Configure aqui a estrutura final da planilha. O sistema detecta se é Bling Cadastro, Bling Estoque, Atualização de Preços ou Universal.')

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown('##### Modelos Bling')
            st.caption('Cadastro de produtos, estoque/saldo e atualização de preços usam contrato real e motor correspondente.')
    with col2:
        with st.container(border=True):
            st.markdown('##### Modelos Universal')
            st.caption('Para marketplace, fornecedor ou qualquer layout final com cabeçalho próprio.')


def _split_models_by_contract(upload) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    df = upload.model_df if isinstance(upload.model_df, pd.DataFrame) else None
    contract_type = str(getattr(upload, 'contract_type', '') or st.session_state.get(MODEL_CONTRACT_TYPE_KEY) or 'universal')
    cadastro = df if contract_type == 'cadastro' else None
    estoque = df if contract_type == 'estoque' else None
    preco = df if contract_type == 'atualizacao_preco' else None
    universal = df if contract_type == 'universal' else None
    return cadastro, estoque, preco, universal


def render_home_bling_models() -> None:
    clear_default_home_models()
    _render_model_type_guidance()

    st.markdown('#### Modelo de destino')
    st.caption('Anexe abaixo o modelo que será preenchido no final. Pode ser Bling Cadastro, Bling Estoque, Atualização de Preços ou Universal.')

    upload = render_model_upload_box(
        title='Enviar modelo final de destino',
        operation='detectar_contrato_real',
        key='home_model_upload_bling',
        required_model=False,
        caption=None,
    )
    cadastro_model, estoque_model, preco_model, universal_model = _split_models_by_contract(upload)

    if any(isinstance(df, pd.DataFrame) for df in (cadastro_model, estoque_model, preco_model, universal_model)):
        remember_original_model_upload(upload)
        add_audit_event(
            'home_real_contract_model_upload_ready_to_save',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='OK',
            details={
                'contract_type': getattr(upload, 'contract_type', 'universal'),
                'contract_label': getattr(upload, 'contract_label', 'Modelo Universal'),
                'cadastro': df_log_summary(cadastro_model),
                'estoque': df_log_summary(estoque_model),
                'preco': df_log_summary(preco_model),
                'universal': df_log_summary(universal_model),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        save_home_models(cadastro_model, estoque_model, preco_model, universal_model, replace_missing=True)
        auto_forward_after_first_model_upload(_first_valid_df(cadastro_model, estoque_model, preco_model, universal_model), None)

    _render_loaded_summary()


__all__ = ['render_home_bling_models']
