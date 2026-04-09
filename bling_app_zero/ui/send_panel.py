from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_services import BlingServices


def render_send_panel():
    st.subheader("🚀 Enviar para Bling")

    # =========================
    # VALIDAR DF FINAL
    # =========================
    df = st.session_state.get("df_final")

    if df is None or df.empty:
        st.warning("⚠️ Nenhum dado disponível para envio.")
        return

    # =========================
    # TIPO DE ENVIO
    # =========================
    tipo = st.radio(
        "Tipo de envio:",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        horizontal=True,
    )

    # =========================
    # DEPÓSITO (somente estoque)
    # =========================
    deposito_id = None

    if tipo == "Atualização de Estoque":
        deposito_id = st.text_input(
            "ID do Depósito",
            placeholder="Ex: 123456",
        )

    st.markdown("---")

    # =========================
    # BOTÃO ENVIO
    # =========================
    if st.button("🚀 Enviar para Bling", use_container_width=True):
        service = BlingServices()

        rows = df.to_dict(orient="records")

        with st.spinner("Enviando dados para o Bling..."):

            if tipo == "Cadastro de Produtos":
                resultado = service.enviar_produtos(rows)
            else:
                resultado = service.enviar_estoque(
                    rows,
                    deposito_id=deposito_id,
                )

        # =========================
        # RESULTADO
        # =========================
        st.success("✅ Envio finalizado com sucesso!")

        col1, col2 = st.columns(2)
        col1.metric("Sucesso", resultado.get("sucesso", 0))
        col2.metric("Erros", resultado.get("erro", 0))

        # =========================
        # DETALHES DE ERRO
        # =========================
        if resultado.get("detalhes"):
            with st.expander("⚠️ Ver erros detalhados"):
                st.json(resultado["detalhes"])
