from __future__ import annotations

import streamlit as st


def render_origem_dados() -> None:
    st.title("1. Origem dos dados")
    st.info("Etapa de origem carregada com segurança. O fluxo principal está ativo enquanto os painéis completos são recompostos.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 Cadastro de produtos", use_container_width=True):
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()
    with col2:
        if st.button("📊 Atualização de estoque", use_container_width=True):
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()

    st.caption("Correção defensiva: este módulo evita quebra por import ausente em produção.")
