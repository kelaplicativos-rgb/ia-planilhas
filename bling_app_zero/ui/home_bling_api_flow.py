from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status, disconnect
from bling_app_zero.ui.cadastro_wizard_state import CADASTRO_MODELO_KEY
from bling_app_zero.ui.home_wizard_constants import STEP_ORIGEM, WIZARD_STEP_KEY
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_bling_api_flow.py'
PRICE_UPDATE_OPERATION = 'atualizacao_preco'
FINISH_MODE_KEY = 'bling_finish_mode'
FINISH_MODE_API = 'api_direct'
FINISH_MODE_CSV = 'csv_download'
SKIP_DIRECT_BLING_KEY = 'skip_direct_bling_connection_this_flow'
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'
DIRECT_API_CONTRACT_ACTIVE_KEY = 'direct_bling_api_contract_active'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'

DIRECT_OPERATION_LABELS = {
    'cadastro': 'Cadastrar produtos',
    'estoque': 'Atualizar estoque',
    'atualizacao_preco': 'Atualizar preços',
}

API_CONTRACT_COLUMNS = {
    'cadastro': [
        'Nome',
        'Código',
        'Preço',
        'Quantidade',
        'GTIN',
        'Descrição',
        'Marca',
        'Categoria',
        'Imagens',
        'Depósito',
    ],
    'estoque': ['ID produto', 'Código', 'Quantidade', 'Depósito'],
    'atualizacao_preco': ['ID produto', 'Código', 'Preço'],
}

DIRECT_CONTRACT_SESSION_KEYS = (
    DIRECT_API_CONTRACT_KEY,
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'cadastro_wizard_df_modelo',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'cadastro_wizard_df_modelo_estoque',
    'home_modelo_atualizacao_preco_df',
    'df_modelo_atualizacao_preco',
    'modelo_atualizacao_preco_df',
)


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value == 'bling':
        return CONTEXT_BLING_API
    if value in {CONTEXT_BLING_API, CONTEXT_BLING_CSV, CONTEXT_UNIVERSAL}:
        return value
    return CONTEXT_BLING_API


def _direct_operation() -> str:
    choice = normalize_contract_operation(st.session_state.get('direct_bling_operation_choice'))
    if choice in DIRECT_OPERATION_LABELS:
        return choice
    op = normalize_contract_operation(st.session_state.get('home_slim_flow_operation'))
    if op in DIRECT_OPERATION_LABELS:
        return op
    return 'cadastro'


def is_bling_api_entry() -> bool:
    return _entry_context() == CONTEXT_BLING_API


def is_api_direct_mode() -> bool:
    return (
        str(st.session_state.get(FINISH_MODE_KEY) or '').strip() == FINISH_MODE_API
        and bool(connection_status().get('connected'))
        and is_bling_api_entry()
    )


def direct_api_contract_model(operation: str | None = None) -> pd.DataFrame:
    op = normalize_contract_operation(operation or _direct_operation()) or 'cadastro'
    columns = API_CONTRACT_COLUMNS.get(op, API_CONTRACT_COLUMNS['cadastro'])
    return pd.DataFrame(columns=columns)


def clear_direct_api_contract() -> None:
    if not st.session_state.get(DIRECT_API_CONTRACT_ACTIVE_KEY):
        return
    for key in DIRECT_CONTRACT_SESSION_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(DIRECT_API_CONTRACT_ACTIVE_KEY, None)
    st.session_state.pop(MODEL_CONTRACT_TYPE_KEY, None)


def apply_direct_api_contract(operation: str | None = None) -> pd.DataFrame:
    op = normalize_contract_operation(operation or _direct_operation()) or 'cadastro'
    model = direct_api_contract_model(op)
    st.session_state[DIRECT_API_CONTRACT_ACTIVE_KEY] = True
    st.session_state[DIRECT_API_CONTRACT_KEY] = model.copy()
    st.session_state[CADASTRO_MODELO_KEY] = model.copy()
    st.session_state['cadastro_wizard_df_modelo'] = model.copy()
    st.session_state['home_modelo_universal_df'] = model.copy()
    st.session_state['df_modelo_universal'] = model.copy()
    st.session_state['modelo_universal_df'] = model.copy()

    if op == 'cadastro':
        st.session_state['home_modelo_cadastro_df'] = model.copy()
        st.session_state['df_modelo_cadastro'] = model.copy()
        st.session_state['modelo_cadastro_df'] = model.copy()
    elif op == 'estoque':
        st.session_state['home_modelo_estoque_df'] = model.copy()
        st.session_state['df_modelo_estoque'] = model.copy()
        st.session_state['modelo_estoque_df'] = model.copy()
        st.session_state['cadastro_wizard_df_modelo_estoque'] = model.copy()
    elif op == PRICE_UPDATE_OPERATION:
        st.session_state['home_modelo_atualizacao_preco_df'] = model.copy()
        st.session_state['df_modelo_atualizacao_preco'] = model.copy()
        st.session_state['modelo_atualizacao_preco_df'] = model.copy()

    st.session_state['home_slim_flow_operation'] = op
    st.session_state['home_detected_operation'] = op
    st.session_state['operacao_final'] = op
    st.session_state['tipo_operacao_final'] = op
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = op
    return model


def render_same_tab_connect_button(auth_url: str) -> None:
    safe_url = escape(str(auth_url or ''), quote=True)
    if not safe_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora.')
        return
    st.markdown(
        f'''
<a href="{safe_url}" target="_self" style="
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    font-weight:900;
    padding:0.78rem 1rem;
    border-radius:0.78rem;
    border:1px solid rgba(37,99,235,.28);
    color:#ffffff;
    background:#2563eb;
    box-shadow:0 10px 22px rgba(37,99,235,.18);
">
    Conectar ao Bling
</a>
''',
        unsafe_allow_html=True,
    )


def render_bling_connection_step(section_title) -> None:
    section_title(1, 'Bling API')
    with st.container(border=True):
        st.caption('Conecte ao Bling para enviar cadastro, estoque ou preços direto pela API. Este caminho não usa modelo de planilha nem gera CSV Bling.')
        status = connection_status()
        connected = bool(status.get('connected'))

        if connected:
            st.success('Bling conectado. Escolha o tipo de envio direto.')
            operation = st.radio(
                'O que deseja fazer no Bling?',
                options=list(DIRECT_OPERATION_LABELS.keys()),
                format_func=lambda value: DIRECT_OPERATION_LABELS.get(value, value),
                horizontal=True,
                key='direct_bling_operation_choice',
            )
            if str(st.session_state.get(FINISH_MODE_KEY) or '').strip() == FINISH_MODE_API:
                apply_direct_api_contract(operation)

            if st.button('Usar envio direto pela API', use_container_width=True, key='use_direct_bling_mode'):
                st.session_state[FINISH_MODE_KEY] = FINISH_MODE_API
                st.session_state.pop(SKIP_DIRECT_BLING_KEY, None)
                apply_direct_api_contract(operation)
                st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
                set_scroll_target(STEP_ORIGEM)
                st.rerun()

            st.caption('Para gerar arquivo manual, volte para a Home e use Modelo Universal.')
            if st.button('Desconectar Bling', use_container_width=True, key='entry_disconnect_bling'):
                disconnect()
                clear_direct_api_contract()
                st.session_state.pop(FINISH_MODE_KEY, None)
                st.rerun()
            return

        st.warning('Bling não conectado. Conecte para liberar o envio direto pela API.')
        try:
            auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'bling_connection_entry'})
        except Exception:
            auth_url = ''
        render_same_tab_connect_button(auth_url)
        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)
        st.caption('Sem conexão com o Bling, este caminho fica bloqueado. Para gerar arquivo manual, volte para a Home e use Modelo Universal.')
        add_audit_event(
            'bling_api_connection_required',
            area='BLING_API',
            status='AGUARDANDO_CONEXAO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )


__all__ = [
    'CONTEXT_BLING_API',
    'CONTEXT_BLING_CSV',
    'CONTEXT_UNIVERSAL',
    'FINISH_MODE_API',
    'FINISH_MODE_CSV',
    'FINISH_MODE_KEY',
    'HOME_ENTRY_CONTEXT_KEY',
    'PRICE_UPDATE_OPERATION',
    'SKIP_DIRECT_BLING_KEY',
    'apply_direct_api_contract',
    'clear_direct_api_contract',
    'is_api_direct_mode',
    'is_bling_api_entry',
    'render_bling_connection_step',
]
