from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_oauth import build_authorization_url, disconnect
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

MODEL_DESCRIPTIONS = {
    'cadastro': 'Modelo oficial do Bling para cadastro de produtos.',
    'estoque': 'Modelo oficial do Bling para saldo e atualização de estoque.',
    'precos': 'Modelo oficial do Bling para atualização de preços, inclusive ZIP original.',
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


def _session_has_bling_token() -> bool:
    token = st.session_state.get('bling_oauth_token_response')
    return isinstance(token, dict) and bool(token.get('access_token'))


def _render_master_intro() -> None:
    st.markdown(
        '''
<div style="padding:1.05rem 1.15rem;border:1px solid #e5e7eb;border-radius:20px;background:linear-gradient(135deg,#ffffff 0%,#f8fafc 62%,#eef6ff 100%);box-shadow:0 18px 42px rgba(15,23,42,.055);margin-bottom:1rem;">
  <div style="font-size:.74rem;font-weight:900;color:#475569;text-transform:uppercase;letter-spacing:.12em;">MapeiaAI · Modelos Bling</div>
  <div style="font-size:1.35rem;font-weight:950;color:#0f172a;line-height:1.12;margin-top:.35rem;">Salve os modelos oficiais uma vez e reutilize no fluxo certo.</div>
  <div style="font-size:.96rem;color:#64748b;line-height:1.48;margin-top:.5rem;">Cadastro, estoque e atualização de preços ficam separados para evitar mistura de fluxo.</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _render_bling_connection() -> None:
    # Não consulta Firestore/SQLite aqui para não travar a tela de modelos.
    # O status persistente é tratado no callback; esta área deve ser sempre leve.
    with st.expander('Conexão com Bling', expanded=False):
        if _session_has_bling_token():
            st.success('Bling conectado nesta sessão')
            if st.button('Desconectar Bling', key='disconnect_bling_oauth', use_container_width=True):
                disconnect()
                st.rerun()
            return

        st.caption('Conecte sua conta Bling quando quiser usar integração via API. Os modelos abaixo continuam funcionando sem conexão.')
        try:
            auth_url = build_authorization_url()
        except Exception as exc:
            auth_url = ''
            st.warning('Não consegui gerar o link de conexão agora. Confira os Secrets do Bling no Streamlit.')
            st.caption(f'Detalhe técnico: {exc}')

        if auth_url:
            st.link_button('Conectar ao Bling', auth_url, use_container_width=True)
        else:
            st.warning('Informe o Client ID do Bling nos Secrets para habilitar o botão de conexão.')


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


def _render_model_card(model_type: str) -> None:
    title = MODEL_TITLES.get(model_type, MODEL_LABELS.get(model_type, model_type))
    description = MODEL_DESCRIPTIONS.get(model_type, '')
    upload_label = MODEL_UPLOAD_LABELS.get(model_type, f'Anexar ou substituir {title}')
    upload_help = MODEL_UPLOAD_HELP.get(model_type, 'Anexe o arquivo oficial do Bling. O sistema valida o conteúdo após o upload.')

    with st.container(border=True):
        st.markdown(f'#### {title}')
        st.caption(description)

        if model_type == PRICE_MODEL_TYPE:
            st.warning(PRICE_MODEL_WARNING)

        try:
            df, info = get_user_model(model_type)
        except Exception as exc:
            df, info = None, None
            st.warning(f'Não consegui carregar este modelo salvo agora: {exc}')

        if df is not None and info:
            st.success('Modelo salvo')
            st.caption(str(info.get('name') or ''))
            if info.get('format'):
                st.caption('Formato: ' + str(info.get('format')).upper())
            st.caption('Colunas: ' + str(len(df.columns)))

            if model_type == PRICE_MODEL_TYPE:
                if st.button('Usar e ir para mapeamento', key=f'use_{model_type}', use_container_width=True):
                    _go_to_origin(model_type)
            elif st.button('Usar e ir para Origem', key=f'use_{model_type}', use_container_width=True):
                _go_to_origin(model_type)

            if st.button('Remover modelo salvo', key=f'remove_{model_type}', use_container_width=True):
                remove_user_model(model_type)
                st.rerun()
        else:
            st.warning('Nenhum modelo salvo ainda.')

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
                    st.success('Modelo de preços salvo. Abrindo mapeamento...')
                    _set_price_update_flow(STEP_MAPEAMENTO)
                    st.rerun()
                else:
                    st.success('Modelo salvo. Indo para Origem dos dados...')
                    _go_to_origin(model_type)
            except Exception as exc:
                st.error(f'Arquivo não aceito: {exc}')


def render_modelos_bling_user_screen() -> None:
    _render_master_intro()
    _render_bling_connection()

    st.markdown('### Modelos oficiais do Bling')
    st.caption('Escolha o tipo de modelo, anexe o arquivo original e siga para o fluxo correspondente.')

    for model_type in MODEL_TYPES:
        _render_model_card(model_type)


__all__ = ['render_modelos_bling_user_screen']
