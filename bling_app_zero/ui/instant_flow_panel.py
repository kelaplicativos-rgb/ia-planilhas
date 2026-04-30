import streamlit as st
from bling_app_zero.core.instant_scraper.flow_contract import InstantFlowState


def render_instant_flow(state: InstantFlowState):
    st.markdown("### 🚀 Status da Busca")

    col1, col2, col3 = st.columns(3)

    col1.metric("Status", state.status)
    col2.metric("Produtos", state.total_produtos)
    col3.metric("Candidatos", state.candidatos_detectados)

    st.caption(f"Modo: {state.modo_runtime} | Browser: {state.browser_disponivel}")

    if state.erro:
        st.error(state.erro)

    if st.button("🔄 Reprocessar"):
        st.session_state.pop("df_origem", None)
        st.session_state.pop("instant_candidates", None)
        st.rerun()
