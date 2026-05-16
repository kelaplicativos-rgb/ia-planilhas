from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.universal_flow import render_universal_flow

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_INTAKE_MODEL_KEY = 'mapeiaai_home_intake_model_df'
HOME_INTAKE_MODEL_FILE_KEY = 'mapeiaai_home_intake_model_file'
FLOW_UNIVERSAL = 'universal_model_flow'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'


def _set_flow(flow: str) -> None:
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    add_audit_event(
        'home_model_contract_received',
        area='HOME',
        details={'previous': previous, 'selected': flow, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operation_v2'] = flow
    except Exception:
        pass
    st.rerun()


def _clear_flow_query_param() -> None:
    for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _current_flow() -> str:
    allowed = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if allowed and flow:
        return flow

    stale_flow = st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    if stale_flow:
        add_audit_event(
            'home_stale_flow_cleared',
            area='HOME',
            details={'reason': 'home_must_start_on_sheet_contract_upload', 'stale_flow': stale_flow, 'responsible_file': RESPONSIBLE_FILE},
        )
    return ''


def _read_intake_file(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        df = read_upload_fast(uploaded_file)
    except Exception as exc:
        st.error(f'Não consegui ler essa planilha: {exc}')
        return None
    if not isinstance(df, pd.DataFrame) or df.empty or not len(df.columns):
        st.warning('Arquivo recebido, mas não encontrei uma tabela válida para mapear.')
        return None
    return df.fillna('')


def _store_contract_model(df: pd.DataFrame, file_name: str) -> None:
    clean_df = df.copy().fillna('')
    st.session_state[HOME_INTAKE_MODEL_KEY] = clean_df
    st.session_state[HOME_INTAKE_MODEL_FILE_KEY] = file_name
    st.session_state['mapeiaai_universal_model_df'] = clean_df
    st.session_state['mapeiaai_final_contract_df'] = clean_df


def _render_contract_preview(df: pd.DataFrame, file_name: str) -> None:
    st.success('Planilha recebida como contrato final de saída.')
    st.caption('O sistema não precisa adivinhar se é Kyte, Olist, Magalu, cadastro, estoque ou ERP próprio. O arquivo anexado define as colunas finais.')
    st.caption(f'Arquivo: {file_name} · {len(df.columns)} coluna(s)')
    with st.expander('Conferir contrato da planilha final', expanded=False):
        st.dataframe(df.head(8).astype(str), use_container_width=True, height=220)
        st.caption(', '.join(map(str, df.columns)))

    if st.button('Continuar para origem dos dados', use_container_width=True, key='home_continue_after_contract_upload'):
        add_audit_event(
            'home_contract_continue_clicked',
            area='HOME',
            details={
                'file_name': file_name,
                'columns_count': int(len(df.columns)),
                'flow': FLOW_UNIVERSAL,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _set_flow(FLOW_UNIVERSAL)


def _render_operation_choice() -> None:
    st.markdown('## Anexe a planilha que vai ser mapeada')
    st.caption(
        'Envie a planilha/modelo de destino. Ela vira o contrato fiel do download final, independente do sistema, fornecedor ou marketplace.'
    )

    uploaded = st.file_uploader(
        'Planilha que vai ser mapeada',
        type=None,
        accept_multiple_files=False,
        key='home_single_model_intake_upload',
        help='No celular o seletor fica livre para evitar bloqueio falso de CSV/planilhas válidas. A validação acontece dentro do MapeiaAI.',
    )
    df = _read_intake_file(uploaded)
    if not isinstance(df, pd.DataFrame):
        st.info('Anexe a planilha para liberar o próximo passo.')
        st.caption('Depois você escolhe a origem dos dados, faz o mapeamento com IA real, aplica opcionais de cálculo e baixa o arquivo no mesmo contrato anexado.')
        return

    file_name = str(getattr(uploaded, 'name', 'planilha')).strip()
    _store_contract_model(df, file_name)
    add_audit_event(
        'home_contract_model_uploaded',
        area='HOME',
        details={
            'file_name': file_name,
            'columns_count': int(len(df.columns)),
            'flow': FLOW_UNIVERSAL,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    _render_contract_preview(df, file_name)


def _back_to_operations() -> None:
    st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    add_audit_event('home_contract_flow_cleared', area='HOME', details={'kept_contract': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _render_back_to_operations() -> None:
    if st.button('← Voltar', use_container_width=True, key='home_back_to_operation_choice'):
        _back_to_operations()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    _render_back_to_operations()
    render_universal_flow()


__all__ = ['render_home_router']
