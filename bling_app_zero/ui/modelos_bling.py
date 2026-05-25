from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_models import (
    DESTINATION_MODEL_UPLOAD_BYTES_KEY,
    DESTINATION_MODEL_UPLOAD_NAME_KEY,
    save_home_models,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/modelos_bling.py'
ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD = 'wizard_cadastro_estoque'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_ORIGEM = 'origem'
QUICK_MODEL_READY_KEY = 'bling_quick_model_ready_origin'
UNIVERSAL_OPERATION = 'universal'

BLING_LINKS = (
    ('Abrir Bling', 'https://www.bling.com.br/'),
    ('Importador de preços multiloja', 'https://www.bling.com.br/importador.precos.produtos.multiloja.php'),
    ('Central de ajuda Bling', 'https://ajuda.bling.com.br/'),
)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, sep=';', index=False)
    return buffer.getvalue().encode('utf-8-sig')


def _modelo_cadastro() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Preco unitario', 'Unidade', 'GTIN EAN', 'Marca', 'Categoria', 'URL imagens'])


def _modelo_estoque() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Deposito', 'Quantidade', 'Observacoes'])


def _modelo_precos() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Loja', 'Preco atual', 'Novo preco', 'Margem'])


def _set_query_flow_to_origin() -> None:
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _activate_model_and_go_to_origin(*, model_type: str, df_model: pd.DataFrame, file_name: str) -> None:
    df_model = df_model.copy().fillna('')
    file_bytes = _csv_bytes(df_model)

    if model_type == 'estoque':
        save_home_models(None, df_model, replace_missing=True)
    else:
        save_home_models(df_model, None, replace_missing=True)

    st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = file_name
    st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = file_bytes
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
    st.session_state[QUICK_MODEL_READY_KEY] = True
    st.session_state['bling_quick_model_type'] = model_type
    st.session_state['home_slim_flow_operation'] = UNIVERSAL_OPERATION
    st.session_state['operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['tipo_operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['home_detected_operation'] = UNIVERSAL_OPERATION

    add_audit_event(
        'bling_quick_model_loaded_go_to_origin',
        area='MODELOS_BLING',
        step=STEP_ORIGEM,
        status='OK',
        details={
            'model_type': model_type,
            'file_name': file_name,
            'columns': [str(column) for column in df_model.columns],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    _set_query_flow_to_origin()
    st.rerun()


def _render_bling_links() -> None:
    st.markdown('#### Atalhos Bling')
    st.caption('Todos os links referentes ao Bling ficam concentrados nesta aba.')
    for label, url in BLING_LINKS:
        st.link_button(label, url, use_container_width=True)


def _render_quick_flows(cadastro: pd.DataFrame, estoque: pd.DataFrame) -> None:
    st.markdown('#### Ir direto para origem dos dados')
    st.caption('Abre o fluxo Universal já com o modelo Bling interno carregado.')

    col1, col2 = st.columns(2)
    with col1:
        if st.button('Cadastro de produtos', use_container_width=True, key='bling_quick_cadastro_origin'):
            _activate_model_and_go_to_origin(
                model_type='cadastro',
                df_model=cadastro,
                file_name='modelo_bling_cadastro.csv',
            )
    with col2:
        if st.button('Atualização de estoque', use_container_width=True, key='bling_quick_estoque_origin'):
            _activate_model_and_go_to_origin(
                model_type='estoque',
                df_model=estoque,
                file_name='modelo_bling_estoque.csv',
            )


def _render_model_downloads(cadastro: pd.DataFrame, estoque: pd.DataFrame, precos: pd.DataFrame) -> None:
    st.markdown('#### Modelos base')
    st.caption('Baixe modelos base para cadastro, estoque e atualização de preços.')

    st.download_button('Baixar cadastro', data=_csv_bytes(cadastro), file_name='modelo_bling_cadastro.csv', mime='text/csv', use_container_width=True)
    st.download_button('Baixar estoque', data=_csv_bytes(estoque), file_name='modelo_bling_estoque.csv', mime='text/csv', use_container_width=True)
    st.download_button('Baixar preços', data=_csv_bytes(precos), file_name='modelo_bling_precos.csv', mime='text/csv', use_container_width=True)


def render_modelos_bling() -> None:
    add_audit_event(
        'modelos_bling_rendered',
        area='MODELOS_BLING',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    st.markdown('### Bling')
    st.caption('Área exclusiva para modelos, atalhos e informações referentes ao Bling.')

    cadastro = _modelo_cadastro()
    estoque = _modelo_estoque()
    precos = _modelo_precos()

    _render_bling_links()
    st.markdown('---')
    _render_quick_flows(cadastro, estoque)
    st.markdown('---')
    _render_model_downloads(cadastro, estoque, precos)

    with st.expander('Ver colunas dos modelos', expanded=False):
        st.caption('Cadastro')
        st.dataframe(cadastro, use_container_width=True, hide_index=True)
        st.caption('Estoque')
        st.dataframe(estoque, use_container_width=True, hide_index=True)
        st.caption('Preços')
        st.dataframe(precos, use_container_width=True, hide_index=True)

    st.warning('Esses modelos são bases internas. Quando você anexar um modelo oficial no fluxo Universal, o sistema deve respeitar o arquivo anexado.')


__all__ = ['render_modelos_bling']
