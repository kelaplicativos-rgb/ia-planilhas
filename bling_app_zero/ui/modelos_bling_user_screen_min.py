from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.user_bling_models_store import (
    MODEL_LABELS,
    MODEL_TYPES,
    get_user_model,
    remove_user_model,
    save_user_model,
)

FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
UNIVERSAL_OPERATION = 'universal'
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
    'cadastro': 'Anexe o arquivo oficial do Bling em CSV, XLSX, XLS, XLSM ou XLSB. Depois ele ficará salvo para reutilizar, remover ou substituir.',
    'estoque': 'Anexe o arquivo oficial do Bling em CSV, XLSX, XLS, XLSM ou XLSB. Depois ele ficará salvo para reutilizar, remover ou substituir.',
    'precos': 'Aceita o arquivo original do Bling, inclusive quando vier compactado em ZIP. O sistema extrai a planilha interna e salva o modelo para atualização de preços.',
}

PRICE_MODEL_WARNING = (
    'Atualização de preços aceita o formato original do Bling, inclusive ZIP. '
    'Depois de salvo, o modelo será usado no fluxo próprio de atualização de preços.'
)


def _go_to_origin(model_type: str) -> None:
    if model_type == PRICE_MODEL_TYPE:
        st.session_state['bling_price_model_waiting_own_flow'] = True
        st.session_state['home_slim_flow_operation'] = 'atualizacao_preco'
        st.session_state['home_detected_operation'] = 'atualizacao_preco'
        st.session_state['operacao_final'] = 'atualizacao_preco'
        st.session_state['tipo_operacao_final'] = 'atualizacao_preco'
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
    st.caption('Pode anexar o ZIP original baixado do Bling. O sistema vai procurar a planilha dentro do pacote automaticamente.')


def _show_model(model_type: str) -> None:
    label = MODEL_LABELS.get(model_type, model_type)
    title = MODEL_TITLES.get(model_type, label)
    upload_label = MODEL_UPLOAD_LABELS.get(model_type, f'Anexar ou substituir {label}')
    upload_help = MODEL_UPLOAD_HELP.get(model_type, 'Anexe o arquivo oficial do Bling apenas uma vez. Depois ele ficará disponível para reutilizar, remover ou substituir.')

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
            st.button('Modelo de preços salvo para o fluxo próprio', key=f'use_{model_type}', use_container_width=True, disabled=True)
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
        type=['csv', 'xlsx', 'xls', 'xlsm', 'xlsb', 'zip'],
        help=upload_help,
    )

    if uploaded is not None:
        try:
            save_user_model(model_type, uploaded.name, uploaded.getvalue())
            if model_type == PRICE_MODEL_TYPE:
                st.success('Modelo Bling de atualização de preços salvo com sucesso. ZIP original aceito quando houver planilha interna válida.')
                st.warning(PRICE_MODEL_WARNING)
            else:
                st.success('Modelo Bling salvo com sucesso. Indo para Origem dos dados...')
                _go_to_origin(model_type)
        except Exception as exc:
            st.error(f'Arquivo não aceito: {exc}')


def render_modelos_bling_user_screen() -> None:
    st.markdown('### Modelos Bling')
    st.caption('Cadastre uma vez os modelos oficiais do Bling e reutilize quando precisar.')
    st.info('Esta área é somente para modelos do Bling. Para preencher um modelo próprio, use Modelos Universal na Home.')

    for model_type in MODEL_TYPES:
        _show_model(model_type)


__all__ = ['render_modelos_bling_user_screen']
