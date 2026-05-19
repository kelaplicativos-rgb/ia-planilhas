from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.business_config import APP_PUBLIC_DOMAIN, CREDIT_PACKAGES, credit_price_label
from bling_app_zero.core.credits import COST_PER_MAPPED_SHEET, CREDITS_ENABLED_KEY, add_demo_credits, get_credit_balance


def render_credits_sidebar() -> None:
    with st.sidebar:
        with st.expander('💳 Créditos MapeiaAI', expanded=False):
            st.caption(f'Modelo preparado: {credit_price_label()}. Integração real ainda não está conectada.')
            st.toggle('Ativar controle de créditos', key=CREDITS_ENABLED_KEY, value=bool(st.session_state.get(CREDITS_ENABLED_KEY, False)))
            st.metric('Saldo', f'{get_credit_balance()} crédito(s)')
            st.caption(f'Custo por planilha mapeada: {COST_PER_MAPPED_SHEET} crédito')

            st.markdown('##### Pacotes planejados')
            st.dataframe(pd.DataFrame(CREDIT_PACKAGES), use_container_width=True, hide_index=True, height=145)

            st.markdown('##### Ambiente de teste')
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button('+5 créditos', use_container_width=True, key='mapeiaai_add_5_demo_credits'):
                    add_demo_credits(5)
                    st.rerun()
            with col_b:
                if st.button('+20 créditos', use_container_width=True, key='mapeiaai_add_20_demo_credits'):
                    add_demo_credits(20)
                    st.rerun()
            st.caption(f'Produção: configurar painel em {APP_PUBLIC_DOMAIN} e salvar o saldo por usuário.')


__all__ = ['render_credits_sidebar']
