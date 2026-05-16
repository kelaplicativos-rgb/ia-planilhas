from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_models import save_home_models
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.universal_flow import render_universal_flow
from bling_app_zero.universal.model_detector import (
    MODEL_TYPE_CADASTRO,
    MODEL_TYPE_ESTOQUE,
    MODEL_TYPE_MULTILOJAS,
    MODEL_TYPE_PERSONALIZADO,
    MODEL_TYPE_PRECOS,
    detect_model_type,
)
from bling_app_zero.v2.price_multistore.ui_plus import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_INTAKE_MODEL_KEY = 'mapeiaai_home_intake_model_df'
HOME_INTAKE_MODEL_TYPE_KEY = 'mapeiaai_home_intake_model_type'
HOME_INTAKE_MODEL_FILE_KEY = 'mapeiaai_home_intake_model_file'
FLOW_UNIVERSAL = 'universal_model_flow'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_MULTISTORE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'


@dataclass(frozen=True)
class IntakeDecision:
    flow: str
    operation: str
    label: str
    reason: str


def _set_flow(flow: str) -> None:
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    add_audit_event(
        'home_operation_selected',
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
            details={'reason': 'home_must_start_on_sheet_intake', 'stale_flow': stale_flow, 'responsible_file': RESPONSIBLE_FILE},
        )
    return ''


def _decision_for_model_type(model_type: str) -> IntakeDecision:
    if model_type == MODEL_TYPE_ESTOQUE:
        return IntakeDecision(FLOW_WIZARD, 'estoque', 'Atualizar estoque', 'O modelo contém campos de estoque, saldo, quantidade ou depósito.')
    if model_type == MODEL_TYPE_CADASTRO:
        return IntakeDecision(FLOW_WIZARD, 'cadastro', 'Cadastrar produtos', 'O modelo contém campos de cadastro de produto.')
    if model_type in {MODEL_TYPE_PRECOS, MODEL_TYPE_MULTILOJAS}:
        return IntakeDecision(FLOW_PRICE_MULTISTORE, 'precos', 'Preços multiloja', 'O modelo contém campos de preço, loja, canal ou marketplace.')
    return IntakeDecision(FLOW_UNIVERSAL, 'personalizado', 'Modelo universal', 'O modelo será tratado como layout personalizado e a planilha final seguirá exatamente o anexo.')


def _store_intake_model(df: pd.DataFrame, file_name: str, model_type: str) -> None:
    st.session_state[HOME_INTAKE_MODEL_KEY] = df.copy().fillna('')
    st.session_state[HOME_INTAKE_MODEL_TYPE_KEY] = model_type
    st.session_state[HOME_INTAKE_MODEL_FILE_KEY] = file_name
    st.session_state['mapeiaai_universal_model_df'] = df.copy().fillna('')
    st.session_state['mapeiaai_price_model_df'] = df.copy().fillna('')

    if model_type == MODEL_TYPE_ESTOQUE:
        save_home_models(None, df, replace_missing=False)
    elif model_type == MODEL_TYPE_CADASTRO:
        save_home_models(df, None, replace_missing=False)


def _apply_decision(decision: IntakeDecision) -> None:
    if decision.operation in {'cadastro', 'estoque'}:
        st.session_state['home_slim_flow_operation'] = decision.operation
        st.session_state['operacao_final'] = decision.operation
        st.session_state['tipo_operacao_final'] = decision.operation
    elif decision.operation == 'precos':
        st.session_state['home_slim_flow_operation'] = 'precos'
        st.session_state['operacao_final'] = 'precos'
        st.session_state['tipo_operacao_final'] = 'precos'
    _set_flow(decision.flow)


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


def _render_intake_preview(df: pd.DataFrame, model_type: str, decision: IntakeDecision) -> None:
    st.success(f'Tipo detectado: {decision.label}')
    st.caption(decision.reason)
    st.caption(f'Colunas encontradas: {len(df.columns)}')
    with st.expander('Conferir planilha anexada', expanded=False):
        st.dataframe(df.head(8).astype(str), use_container_width=True, height=220)
        st.caption(', '.join(map(str, df.columns)))

    if st.button(f'Continuar para {decision.label}', use_container_width=True, key='home_continue_after_intake_upload'):
        add_audit_event(
            'home_intake_continue_clicked',
            area='HOME',
            details={
                'model_type': model_type,
                'flow': decision.flow,
                'operation': decision.operation,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _apply_decision(decision)


def _render_operation_choice() -> None:
    st.markdown('## Anexe a planilha que vai ser mapeada')
    st.caption('Envie o modelo/planilha de destino. O MapeiaAI detecta se é cadastro, estoque, preços multiloja ou modelo personalizado e segue para o fluxo normal.')

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
        st.caption('Depois disso, o sistema mantém o fluxo normal: origem dos dados, busca por site quando aplicável, calculadora, mapeamento, preview e download final.')
        return

    detection = detect_model_type(df)
    model_type = detection.model_type
    decision = _decision_for_model_type(model_type)
    file_name = str(getattr(uploaded, 'name', 'planilha')).strip()
    _store_intake_model(df, file_name, model_type)

    add_audit_event(
        'home_intake_model_detected',
        area='HOME',
        details={
            'file_name': file_name,
            'model_type': model_type,
            'confidence': detection.confidence,
            'columns_count': int(len(df.columns)),
            'flow': decision.flow,
            'operation': decision.operation,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    _render_intake_preview(df, model_type, decision)


def _back_to_operations() -> None:
    st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    add_audit_event('home_operation_cleared', area='HOME', details={'kept_wizard_progress': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _render_back_to_operations() -> None:
    if st.button('← Voltar', use_container_width=True, key='home_back_to_operation_choice'):
        _back_to_operations()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    if flow == FLOW_UNIVERSAL:
        _render_back_to_operations()
        render_universal_flow()
        return

    if flow == FLOW_PRICE_MULTISTORE:
        _render_back_to_operations()
        render_price_multistore_v2()
        return

    render_home_wizard()


__all__ = ['render_home_router']
