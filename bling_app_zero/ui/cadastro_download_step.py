from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    BLING_IMPORTADOR_PRODUTOS_URL,
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    render_supplier_price_master_notice,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final


def render_cadastro_download_step() -> None:
    st.markdown('### Download do cadastro')
    st.caption('Última etapa: baixe somente o CSV final de cadastro pronto para o Bling.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('Ainda não há CSV final de cadastro. Volte para o preview.')
        return

    render_supplier_price_master_notice(df_final)

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


__all__ = ['render_cadastro_download_step']
