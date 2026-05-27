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
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'
BLING_CONTRACTS = {'cadastro', 'estoque', 'atualizacao_preco'}


def _entry_context() -> str:
    return str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()


def _is_universal_entry() -> bool:
    return _entry_context() == CONTEXT_UNIVERSAL


def _is_bling_csv_entry() -> bool:
    return _entry_context() == CONTEXT_BLING_CSV


def _model_summary_df() -> pd.DataFrame | None:
    if _is_universal_entry():
        df = get_home_universal_model()
        return df if isinstance(df, pd.DataFrame) else None
    if _is_bling_csv_entry():
        for df in (get_home_cadastro_model(), get_home_estoque_model(), get_home_preco_model()):
            if isinstance(df, pd.DataFrame):
                return df
        return None
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
        if _is_universal_entry():
            st.warning('Envie o modelo universal de destino para continuar. Use uma planilha com as colunas finais que o sistema deverá preencher.')
        elif _is_bling_csv_entry():
            st.warning('Envie um modelo oficial do Bling para continuar: Cadastro, Estoque ou Atualização de Preços.')
        else:
            st.warning('Envie o modelo final de destino para continuar.')
        return
    contract_type = str(st.session_state.get(MODEL_CONTRACT_TYPE_KEY) or 'universal')
    if _is_universal_entry():
        label = 'Modelo Universal'
    else:
        label = CONTRACT_LABELS.get(contract_type, CONTRACT_LABELS['universal'])
    st.caption(f'{label} carregado · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo de destino', expanded=False):
        columns = [str(column) for column in list(df.columns)]
        st.caption(', '.join(columns))


def _render_model_type_guidance() -> None:
    if _is_universal_entry():
        st.markdown('#### Modelo Universal')
        st.caption('Configure somente um modelo universal com cabeçalho próprio. Este caminho não usa modelos oficiais do Bling.')
        with st.container(border=True):
            st.markdown('##### Estrutura universal')
            st.caption('Use para marketplace, fornecedor ou qualquer layout final personalizado.')
        return

    st.markdown('#### Modelos Bling')
    st.caption('Configure a estrutura oficial do Bling para gerar CSV de importação manual.')
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown('##### Cadastro')
            st.caption('Produtos completos para cadastro/importação.')
    with col2:
        with st.container(border=True):
            st.markdown('##### Estoque')
            st.caption('Saldo, depósito e atualização de quantidade.')
    with col3:
        with st.container(border=True):
            st.markdown('##### Preços')
            st.caption('Atualização de valores de venda.')


def _split_models_by_contract(upload) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    df = upload.model_df if isinstance(upload.model_df, pd.DataFrame) else None
    if _is_universal_entry():
        st.session_state[MODEL_CONTRACT_TYPE_KEY] = 'universal'
        return None, None, None, df

    contract_type = str(getattr(upload, 'contract_type', '') or st.session_state.get(MODEL_CONTRACT_TYPE_KEY) or '').strip()
    if _is_bling_csv_entry() and contract_type not in BLING_CONTRACTS:
        if isinstance(df, pd.DataFrame):
            st.warning('Este caminho é Bling CSV. Envie um modelo oficial do Bling: Cadastro, Estoque ou Atualização de Preços.')
        return None, None, None, None

    cadastro = df if contract_type == 'cadastro' else None
    estoque = df if contract_type == 'estoque' else None
    preco = df if contract_type == 'atualizacao_preco' else None
    universal = df if contract_type == 'universal' and not _is_bling_csv_entry() else None
    return cadastro, estoque, preco, universal


def render_home_bling_models() -> None:
    clear_default_home_models()
    _render_model_type_guidance()

    if _is_universal_entry():
        st.markdown('#### Modelo de destino universal')
        st.caption('Anexe o modelo universal que será preenchido no final.')
        title = 'Enviar modelo universal de destino'
        operation = 'universal'
    else:
        st.markdown('#### Modelo oficial Bling')
        st.caption('Anexe o modelo Bling de Cadastro, Estoque ou Atualização de Preços que será preenchido no final.')
        title = 'Enviar modelo Bling'
        operation = 'detectar_contrato_real'

    upload = render_model_upload_box(
        title=title,
        operation=operation,
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
                'entry_context': _entry_context(),
                'contract_type': 'universal' if _is_universal_entry() else getattr(upload, 'contract_type', 'universal'),
                'contract_label': 'Modelo Universal' if _is_universal_entry() else getattr(upload, 'contract_label', 'Modelo Universal'),
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
