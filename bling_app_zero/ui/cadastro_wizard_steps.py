from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.cadastro_mapping import render_manual_mapping
from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.cadastro_sources import (
    render_cadastro_source_upload,
    select_cadastro_model,
    select_estoque_model_for_cadastro,
)
from bling_app_zero.ui.home_shared import df_signature, download_final, preview_df, show_mapping

CADASTRO_SOURCE_SIGNATURE_KEY = 'cadastro_source_signature_atual'
CADASTRO_ORIGEM_KEY = 'cadastro_wizard_df_origem'
CADASTRO_ORIGEM_PRICED_KEY = 'cadastro_wizard_df_para_mapear'
CADASTRO_MODELO_KEY = 'cadastro_wizard_df_modelo'
CADASTRO_MODELO_ESTOQUE_KEY = 'cadastro_wizard_df_modelo_estoque'


def _source_dataframe(df_origem_site: pd.DataFrame | None, upload) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame):
        return df_origem_site
    source_df = getattr(upload, 'source_df', None)
    return source_df if isinstance(source_df, pd.DataFrame) else None


def _clear_cadastro_outputs_if_source_changed(df_origem: pd.DataFrame | None) -> None:
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return
    signature = df_signature(df_origem)
    previous = st.session_state.get(CADASTRO_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    for key in [
        'df_final_cadastro',
        'mapping_cadastro',
        'mapping_confidence_cadastro',
        'df_origem_cadastro_precificada',
        'df_final_estoque_from_cadastro',
        'mapping_estoque_from_cadastro',
        'mapping_confidence_estoque_from_cadastro',
        CADASTRO_ORIGEM_PRICED_KEY,
    ]:
        st.session_state.pop(key, None)
    st.session_state[CADASTRO_SOURCE_SIGNATURE_KEY] = signature


def _store_cadastro_context(
    df_origem: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> None:
    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        st.session_state[CADASTRO_ORIGEM_KEY] = df_origem
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        st.session_state[CADASTRO_MODELO_KEY] = df_modelo
    if isinstance(df_modelo_estoque, pd.DataFrame) and len(df_modelo_estoque.columns):
        st.session_state[CADASTRO_MODELO_ESTOQUE_KEY] = df_modelo_estoque


def cadastro_context_ready() -> bool:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    return isinstance(df_origem, pd.DataFrame) and not df_origem.empty


def cadastro_mapping_ready() -> bool:
    df_final = st.session_state.get('df_final_cadastro')
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def render_cadastro_entrada_step() -> None:
    st.markdown('### Entrada do cadastro')
    st.caption('Nesta tela entra somente a origem do cadastro. O mapeamento e o download ficam nas próximas etapas.')

    df_origem_site = get_site_source_for_operation('cadastro')
    upload = render_cadastro_source_upload(df_origem_site)
    df_origem = _source_dataframe(df_origem_site, upload)
    _clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)
    _store_cadastro_context(df_origem, df_modelo, df_modelo_estoque)

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        st.success(f'Origem de cadastro carregada com {len(df_origem)} produto(s) e {len(df_origem.columns)} coluna(s).')
        with st.expander('Conferir origem carregada', expanded=False):
            preview_df('Origem do cadastro', df_origem)
        if isinstance(df_modelo, pd.DataFrame):
            st.caption(f'Modelo de cadastro detectado com {len(df_modelo.columns)} coluna(s).')
        if isinstance(df_modelo_estoque, pd.DataFrame):
            st.caption(f'Modelo de estoque também detectado com {len(df_modelo_estoque.columns)} coluna(s).')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.info('Envie a origem do fornecedor ou use a busca por site antes de continuar.')


def render_cadastro_mapeamento_step() -> None:
    st.markdown('### Mapeamento do cadastro')
    st.caption('Aqui só aparece o mapeamento. Preview final e download ficam separados para deixar a tela leve.')

    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning('Nenhuma origem de cadastro carregada. Volte para a etapa Entrada.')
        return

    df_para_mapear = render_cadastro_pricing(df_origem)
    df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
    if isinstance(df_para_mapear, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_para_mapear
    render_manual_mapping(df_para_mapear, df_modelo)


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview final do cadastro')
    st.caption('Confira o CSV final antes de baixar. Esta tela não reabre o mapeamento para evitar carga desnecessária.')

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})

    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    show_mapping(mapping, operation='cadastro')
    preview_df('🧾 CADASTRO · Preview final', df_final)


def render_cadastro_download_step() -> None:
    st.markdown('### Download do cadastro')
    st.caption('Última etapa: baixe somente o CSV final de cadastro pronto para o Bling.')

    df_final = st.session_state.get('df_final_cadastro')
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        st.warning('Ainda não há CSV final de cadastro. Volte para o preview.')
        return

    download_final(df_final, 'cadastro', 'cadastro_wizard')
