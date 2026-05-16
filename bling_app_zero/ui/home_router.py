from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_INTAKE_MODEL_KEY = 'mapeiaai_home_intake_model_df'
HOME_INTAKE_MODEL_FILE_KEY = 'mapeiaai_home_intake_model_file'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
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


def _store_contract_model(df: pd.DataFrame, file_name: str) -> None:
    clean_df = df.copy().fillna('')
    st.session_state[HOME_INTAKE_MODEL_KEY] = clean_df
    st.session_state[HOME_INTAKE_MODEL_FILE_KEY] = file_name
    st.session_state['mapeiaai_final_contract_df'] = clean_df

    # O restante do sistema antigo continua funcionando com os nomes de modelo
    # que ele já conhece. O mesmo contrato fica disponível para cadastro e estoque,
    # sem tentar detectar automaticamente o tipo do anexo.
    st.session_state['home_modelo_cadastro_df'] = clean_df.copy()
    st.session_state['df_modelo_cadastro'] = clean_df.copy()
    st.session_state['modelo_cadastro_df'] = clean_df.copy()
    st.session_state['home_modelo_estoque_df'] = clean_df.copy()
    st.session_state['df_modelo_estoque'] = clean_df.copy()
    st.session_state['modelo_estoque_df'] = clean_df.copy()

    # Entrada padrão no wizard antigo. A partir da segunda etapa, o usuário volta
    # a usar origem por site/anexo, calculadora, mapeamento, preview e download.
    st.session_state.setdefault('home_slim_flow_operation', 'cadastro')
    st.session_state.setdefault('operacao_final', 'cadastro')
    st.session_state.setdefault('tipo_operacao_final', 'cadastro')


def _render_contract_preview(df: pd.DataFrame, file_name: str) -> None:
    st.success('Planilha recebida como modelo/contrato do arquivo final.')
    st.caption('A primeira tela só guarda o modelo anexado. A partir da próxima etapa o sistema volta ao fluxo antigo funcional, com busca por site protegida, origem por anexo, calculadora, mapeamento, preview e download.')
    st.caption(f'Arquivo: {file_name} · {len(df.columns)} coluna(s)')
    with st.expander('Conferir contrato da planilha final', expanded=False):
        st.dataframe(df.head(8).astype(str), use_container_width=True, height=220)
        st.caption(', '.join(map(str, df.columns)))

    if st.button('Continuar para o fluxo do sistema', use_container_width=True, key='home_continue_after_contract_upload'):
        add_audit_event(
            'home_contract_continue_clicked',
            area='HOME',
            details={
                'file_name': file_name,
                'columns_count': int(len(df.columns)),
                'flow': FLOW_WIZARD,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _set_flow(FLOW_WIZARD)


def _render_operation_choice() -> None:
    st.markdown('## Anexe a planilha que vai ser mapeada')
    st.caption(
        'Envie a planilha/modelo de destino. Ela será usada como contrato fiel do download final. Depois o sistema volta ao fluxo antigo completo.'
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
        st.caption('Na próxima etapa voltam os recursos do sistema: buscar produtos por site, anexar origem, calculadora, mapeamento, preview e download final.')
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
