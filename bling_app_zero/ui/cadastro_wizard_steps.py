from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_entry_step import render_cadastro_entrada_step
from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.cadastro_wizard_state import (
    BLING_IMPORTADOR_PRODUTOS_URL,
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    cadastro_context_ready,
    cadastro_mapping_ready,
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.home_shared import download_final, preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping


def render_cadastro_mapeamento_step() -> None:
    st.markdown('### Mapeamento do cadastro')
    st.caption('Conferência das colunas. Preview final e download ficam separados para deixar esta tela mais leve.')

    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    if not valid_df(df_origem):
        st.warning('Nenhuma origem de cadastro carregada. Volte para a etapa Entrada.')
        return
    if not valid_model(df_modelo):
        st.warning('Modelo de cadastro ausente. Volte para a etapa Modelo.')
        return

    store_expected_source_rows(df_origem)
    st.caption(f'Origem em uso no mapeamento: {len(df_origem)} produto(s).')

    df_para_mapear = render_cadastro_pricing(df_origem)
    df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
    if isinstance(df_para_mapear, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_para_mapear
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Precificação aplicada. O campo Preço de venda será usado como base para os campos de preço do Bling.')
    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        render_row_count_blocker(df_final)


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview final do cadastro')
    st.caption('Confira o CSV final antes de baixar. Esta tela não reabre o mapeamento para evitar carga desnecessária.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    mapping = st.session_state.get('mapping_cadastro', {})

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    if render_row_count_blocker(df_final):
        return

    show_mapping(mapping, operation='cadastro')
    preview_df('🧾 CADASTRO · Preview final', df_final)
    render_preview_ai_actions(df_final, 'cadastro')


def render_cadastro_download_step() -> None:
    st.markdown('### Download do cadastro')
    st.caption('Última etapa: baixe somente o CSV final de cadastro pronto para o Bling.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('Ainda não há CSV final de cadastro. Volte para o preview.')
        return

    if render_row_count_blocker(df_final):
        return

    download_final(df_final, 'cadastro', 'cadastro_wizard')

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de produtos do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de produtos no Bling',
        BLING_IMPORTADOR_PRODUTOS_URL,
        use_container_width=True,
    )


__all__ = [
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'render_cadastro_download_step',
    'render_cadastro_entrada_step',
    'render_cadastro_mapeamento_step',
    'render_cadastro_preview_step',
]
