from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.universal.model_detector import (
    MODEL_TYPE_CADASTRO,
    MODEL_TYPE_ESTOQUE,
    MODEL_TYPE_MULTILOJAS,
    MODEL_TYPE_PERSONALIZADO,
    MODEL_TYPE_PRECOS,
    detect_model_type,
)
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_INTAKE_MODEL_KEY = 'mapeiaai_home_intake_model_df'
HOME_INTAKE_MODEL_FILE_KEY = 'mapeiaai_home_intake_model_file'
HOME_INTAKE_MODEL_TYPE_KEY = 'mapeiaai_home_intake_model_type'
HOME_INTAKE_MODEL_CONFIDENCE_KEY = 'mapeiaai_home_intake_model_confidence'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'

CADASTRO_MODEL_KEYS = ('home_modelo_cadastro_df', 'df_modelo_cadastro', 'modelo_cadastro_df')
ESTOQUE_MODEL_KEYS = ('home_modelo_estoque_df', 'df_modelo_estoque', 'modelo_estoque_df')
CADASTRO_SOURCE_KEY = 'home_modelo_cadastro_source'
ESTOQUE_SOURCE_KEY = 'home_modelo_estoque_source'


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
    if not flow:
        try:
            flow = str(st.query_params.get('operation_v2') or '').strip()
        except Exception:
            flow = ''
        if flow:
            st.session_state[ACTIVE_FLOW_KEY] = flow
            st.session_state[HOME_ALLOW_FLOW_KEY] = True
            allowed = True

    if allowed and flow:
        if flow in {FLOW_WIZARD, FLOW_PRICE_UPDATE}:
            return flow
        return FLOW_WIZARD

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


def _clear_model_keys(keys: tuple[str, ...], *, source_key: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)
    st.session_state.pop(source_key, None)


def _write_model_keys(keys: tuple[str, ...], df: pd.DataFrame, *, source_key: str) -> None:
    clean_df = df.copy().fillna('')
    for key in keys:
        st.session_state[key] = clean_df.copy().fillna('')
    st.session_state[source_key] = 'upload'


def _operation_from_model_type(model_type: str) -> str:
    if model_type == MODEL_TYPE_ESTOQUE:
        return 'estoque'
    return 'cadastro'


def _store_contract_model(df: pd.DataFrame, file_name: str) -> None:
    clean_df = df.copy().fillna('')
    detection = detect_model_type(clean_df)
    model_type = detection.model_type
    operation = _operation_from_model_type(model_type)

    st.session_state[HOME_INTAKE_MODEL_KEY] = clean_df
    st.session_state[HOME_INTAKE_MODEL_FILE_KEY] = file_name
    st.session_state[HOME_INTAKE_MODEL_TYPE_KEY] = model_type
    st.session_state[HOME_INTAKE_MODEL_CONFIDENCE_KEY] = float(detection.confidence)
    st.session_state['mapeiaai_final_contract_df'] = clean_df
    st.session_state['home_detected_operation'] = operation

    if model_type == MODEL_TYPE_ESTOQUE:
        _write_model_keys(ESTOQUE_MODEL_KEYS, clean_df, source_key=ESTOQUE_SOURCE_KEY)
        _clear_model_keys(CADASTRO_MODEL_KEYS, source_key=CADASTRO_SOURCE_KEY)
    elif model_type == MODEL_TYPE_CADASTRO:
        _write_model_keys(CADASTRO_MODEL_KEYS, clean_df, source_key=CADASTRO_SOURCE_KEY)
        _clear_model_keys(ESTOQUE_MODEL_KEYS, source_key=ESTOQUE_SOURCE_KEY)
    else:
        _write_model_keys(CADASTRO_MODEL_KEYS, clean_df, source_key=CADASTRO_SOURCE_KEY)
        _write_model_keys(ESTOQUE_MODEL_KEYS, clean_df, source_key=ESTOQUE_SOURCE_KEY)

    st.session_state['home_slim_flow_operation'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation

    try:
        st.query_params['operacao'] = operation
    except Exception:
        pass

    add_audit_event(
        'home_contract_model_detected',
        area='HOME',
        details={
            'file_name': file_name,
            'model_type': model_type,
            'confidence': float(detection.confidence),
            'operation': operation,
            'reason': detection.reason,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _model_type_label(model_type: str) -> str:
    labels = {
        MODEL_TYPE_CADASTRO: 'Cadastro de produtos',
        MODEL_TYPE_ESTOQUE: 'Atualização de estoque',
        MODEL_TYPE_PRECOS: 'Preços',
        MODEL_TYPE_MULTILOJAS: 'Preços por loja/canal',
        MODEL_TYPE_PERSONALIZADO: 'Modelo personalizado',
    }
    return labels.get(model_type, 'Modelo personalizado')


def _render_contract_preview(df: pd.DataFrame, file_name: str) -> None:
    detection = detect_model_type(df)
    operation = _operation_from_model_type(detection.model_type)
    st.success('Planilha recebida como modelo/contrato do arquivo final.')
    st.caption(
        f'Tipo detectado: {_model_type_label(detection.model_type)} · confiança {round(detection.confidence * 100)}%. '
        f'O próximo fluxo começará como {"Estoque" if operation == "estoque" else "Cadastro"}.'
    )
    if detection.model_type in {MODEL_TYPE_PERSONALIZADO, MODEL_TYPE_PRECOS, MODEL_TYPE_MULTILOJAS}:
        st.info(
            'Modelo flexível detectado: ele ficará disponível para cadastro e estoque, sempre respeitando exatamente as colunas anexadas.'
        )
    else:
        st.caption(detection.reason)
    st.caption(f'Arquivo: {file_name} · {len(df.columns)} coluna(s)')
    with st.expander('Conferir contrato da planilha final', expanded=False):
        st.dataframe(df.head(8).astype(str), use_container_width=True, height=220)
        st.caption(', '.join(map(str, df.columns)))

    if st.button('Continuar para o mapeamento', use_container_width=True, key='home_continue_after_contract_upload'):
        add_audit_event(
            'home_contract_continue_clicked',
            area='HOME',
            details={
                'file_name': file_name,
                'columns_count': int(len(df.columns)),
                'flow': FLOW_WIZARD,
                'detected_model_type': detection.model_type,
                'operation': operation,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _set_flow(FLOW_WIZARD)


def _render_operation_choice() -> None:
    st.markdown('## O que você quer mapear hoje?')
    st.caption(
        'Use modelos de marketplaces, ERPs, atualização de estoque, cadastro de produtos, cálculo de lucro e preços multilojas. '
        'O sistema lê a planilha, ajuda no mapeamento e prepara o arquivo certo para importar no ERP ou marketplace em instantes.'
    )

    uploaded = st.file_uploader(
        'Planilha/modelo de destino',
        type=None,
        accept_multiple_files=False,
        key='home_single_model_intake_upload',
        help='No celular o seletor fica livre para evitar bloqueio falso de CSV/planilhas válidas. A validação acontece dentro do MapeiaAI.',
    )
    df = _read_intake_file(uploaded)
    if not isinstance(df, pd.DataFrame):
        st.info('Anexe a planilha ou modelo de destino para liberar o próximo passo.')
        st.caption('Depois disso você continua com site, arquivo, calculadora, regras, mapeamento, preview e download final.')
        return

    file_name = str(getattr(uploaded, 'name', 'planilha')).strip()
    _store_contract_model(df, file_name)
    add_audit_event(
        'home_contract_model_uploaded',
        area='HOME',
        details={
            'file_name': file_name,
            'columns_count': int(len(df.columns)),
            'flow': FLOW_WIZARD,
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
    if flow == FLOW_PRICE_UPDATE:
        render_price_multistore_v2()
        return

    if flow != FLOW_WIZARD:
        st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD

    render_home_wizard()


__all__ = ['FLOW_PRICE_UPDATE', 'FLOW_WIZARD', 'render_home_router']
