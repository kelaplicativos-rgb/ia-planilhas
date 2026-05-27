from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status, disconnect
from bling_app_zero.ui.scroll_position import request_scroll_top
from bling_app_zero.ui.user_bling_models_store import (
    MODEL_LABELS,
    MODEL_TYPES,
    get_user_model,
    remove_user_model,
    save_user_model,
)

FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
STEP_MAPEAMENTO = 'mapeamento'
UNIVERSAL_OPERATION = 'universal'
PRICE_UPDATE_OPERATION = 'atualizacao_preco'
PRICE_MODEL_TYPE = 'precos'

MODEL_TITLES = {
    'cadastro': 'Modelo Bling cadastro',
    'estoque': 'Modelo Bling estoque',
    'precos': 'Modelo Bling atualização de preços',
}

MODEL_UPLOAD_LABELS = {
    'cadastro': 'Anexar ou substituir modelo Bling cadastro',
    'estoque': 'Anexar ou substituir modelo Bling estoque',
    'precos': 'Anexar ou substituir modelo Bling atualização de preços',
}

MODEL_UPLOAD_HELP = {
    'cadastro': 'Anexe o arquivo oficial do Bling. Aceita CSV, XLSX, XLS, XLSM, XLSB e também pacote ZIP quando o Bling entregar compactado.',
    'estoque': 'Anexe o arquivo oficial do Bling. Aceita CSV, XLSX, XLSM, XLS ou XLSB e também pacote ZIP quando o Bling entregar compactado.',
    'precos': 'Anexe o arquivo original baixado do Bling. Pode ser ZIP; o sistema abre o pacote e procura a planilha interna automaticamente.',
}

PRICE_MODEL_WARNING = (
    'Atualização de preços aceita o arquivo original do Bling, inclusive quando vier em ZIP. '
    'Após anexar, o sistema segue direto para a conferência/mapeamento do fluxo de preços.'
)


def _render_bling_connection() -> None:
    status = connection_status()
    with st.container(border=True):
        st.markdown('#### Conexão com Bling')
        if status.get('connected'):
            st.success('Bling conectado')
            connected_at = str(status.get('connected_at') or '').strip()
            if connected_at:
                st.caption(f'Conectado em: {connected_at}')
            if st.button('Desconectar Bling', key='disconnect_bling_oauth', use_container_width=True):
                disconnect()
                st.rerun()
        else:
            st.caption('Conecte sua conta Bling para liberar o fluxo OAuth do sistema.')
            st.link_button('Conectar ao Bling', build_authorization_url(), use_container_width=True)
            st.caption('A autorização abre no Bling e retorna para este app automaticamente.')


def _set_price_update_flow(step: str = STEP_MAPEAMENTO) -> None:
    request_scroll_top()
    st.session_state['bling_price_model_waiting_own_flow'] = False
    st.session_state['home_active_operation_v2'] = FLOW_WIZARD
    st.session_state['home_allow_operation_v2_session'] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['bling_wizard_step'] = step
    st.session_state['bling_quick_model_ready_origin'] = True
    st.session_state['bling_quick_model_type'] = PRICE_MODEL_TYPE
    st.session_state['home_slim_flow_origin'] = 'arquivo'
    st.session_state['origem_final'] = 'arquivo'
    st.session_state['home_slim_flow_operation'] = PRICE_UPDATE_OPERATION
    st.session_state['home_detected_operation'] = PRICE_UPDATE_OPERATION
    st.session_state['operacao_final'] = PRICE_UPDATE_OPERATION
    st.session_state['tipo_operacao_final'] = PRICE_UPDATE_OPERATION
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = step
        st.query_params.pop('flow', None)
        st.query_params.pop('origem', None)
        st.query_params.pop('operacao', None)
    except Exception:
        pass


def _go_to_origin(model_type: str) -> None:
    request_scroll_top()
    if model_type == PRICE_MODEL_TYPE:
        _set_price_update_flow(STEP_MAPEAMENTO)
        st.rerun()
        return

    st.session_state['home_active_operation_v2'] = FLOW_WIZARD
    st.session_state['home_allow_operation_v2_session'] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['bling_wizard_step'] = STEP_ORIGEM
    st.session_state['bling_quick_model_ready_origin'] = True
    st.session_state['bling_quick_model_type'] = model_type
    st.session_state['home_slim_flow_operation'] = UNIVERSAL_OPERATION
    st.session_state['operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['tipo_operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['home_detected_operation'] = UNIVERSAL_OPERATION
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass
    st.rerun()


def _show_price_model_block() -> None:
    st.warning(PRICE_MODEL_WARNING)
    st.caption('Sem bloqueio por extensão no upload: se o arquivo for ZIP original do Bling, o sistema detecta, extrai e avança para mapeamento.')


def _show_model(model_type: str) -> None:
    label = MODEL_LABELS.get(model_type, model_type)
    title = MODEL_TITLES.get(model_type, label)
    upload_label = MODEL_UPLOAD_LABELS.get(model_type, f'Anexar ou substituir {label}')
    upload_help = MODEL_UPLOAD_HELP.get(model_type, 'Anexe o arquivo oficial do Bling. O sistema valida o conteúdo após o upload.')

    st.markdown('---')
    st.markdown(f'#### {title}')

    if model_type == PRICE_MODEL_TYPE:
        _show_price_model_block()

    df, info = get_user_model(model_type)
    if df is not None and info:
        st.success('Modelo Bling salvo')
        st.caption(str(info.get('name') or ''))
        if info.get('format'):
            st.caption('Formato salvo: ' + str(info.get('format')).upper())
        st.caption('Colunas: ' + str(len(df.columns)))
        if model_type == PRICE_MODEL_TYPE:
            if st.button('Usar modelo de preços e ir para mapeamento', key=f'use_{model_type}', use_container_width=True):
                _go_to_origin(model_type)
        elif st.button('Usar este modelo e ir para Origem dos dados', key=f'use_{model_type}', use_container_width=True):
            _go_to_origin(model_type)
        if st.button('Remover modelo salvo', key=f'remove_{model_type}', use_container_width=True):
            remove_user_model(model_type)
            st.rerun()
    else:
        st.warning('Nenhum modelo Bling salvo ainda.')

    uploaded = st.file_uploader(
        upload_label,
        key=f'upload_{model_type}',
        accept_multiple_files=False,
        help=upload_help,
    )

    if uploaded is not None:
        try:
            save_user_model(model_type, uploaded.name, uploaded.getvalue())
            if model_type == PRICE_MODEL_TYPE:
                st.success('Modelo Bling de atualização de preços salvo. Abrindo mapeamento...')
                _set_price_update_flow(STEP_MAPEAMENTO)
                st.rerun()
            else:
                st.success('Modelo Bling salvo com sucesso. Indo para Origem dos dados...')
                _go_to_origin(model_type)
        except Exception as exc:
            st.error(f'Arquivo não aceito: {exc}')


def render_modelos_bling_user_screen() -> None:
    st.markdown('### Modelos Bling')
    st.caption('Cadastre uma vez os modelos oficiais do Bling e reutilize quando precisar.')
    _render_bling_connection()
    st.info('Esta área é somente para modelos do Bling. Para preencher um modelo próprio, use Modelos Universal na Home.')

    for model_type in MODEL_TYPES:
        _show_model(model_type)


__all__ = ['render_modelos_bling_user_screen']
