from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_entry_step import render_cadastro_entrada_step
from bling_app_zero.ui.cadastro_mapping_step import render_cadastro_mapeamento_step
from bling_app_zero.ui.cadastro_wizard_state import (
    BLING_IMPORTADOR_PRODUTOS_URL,
    cadastro_context_ready,
    cadastro_mapping_ready,
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final, preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions


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
