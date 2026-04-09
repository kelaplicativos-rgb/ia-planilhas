from __future__ import annotations

import streamlit as st
import pandas as pd

from bling_app_zero.services.bling_service import BlingService


# =========================
# HELPERS
# =========================
def _get_df_final() -> pd.DataFrame | None:
    try:
        return st.session_state.get("df_saida_final")
    except Exception:
        return None


def _get_tipo_operacao() -> str:
    try:
        return str(st.session_state.get("tipo_operacao_bling") or "").lower()
    except Exception:
        return ""


# =========================
# RENDER PRINCIPAL
# =========================
def render_bling_envio():
    st.subheader("🚀 Envio para Bling")

    df = _get_df_final()
    tipo = _get_tipo_operacao()

    if df is None or not isinstance(df, pd.DataFrame):
        st.warning("⚠️ Nenhum dado disponível para envio.")
        return

    if df.empty:
        st.warning("⚠️ A planilha final está vazia.")
        return

    if not tipo:
        st.warning("⚠️ Tipo de operação não definido.")
        return

    st.success(f"✔ Tipo detectado: {tipo.upper()}")

    # =========================
    # CONFIGURAÇÕES
    # =========================
    deposito_padrao = None

    if tipo == "estoque":
        deposito_padrao = st.text_input(
            "Depósito padrão (obrigatório para estoque)",
            value="",
            help="Ex: ifood, principal, loja1...",
        )

    # =========================
    # BOTÕES
    # =========================
    col1, col2 = st.columns(2)

    service = BlingService()

    with col1:
        if st.button("🔌 Testar conexão"):
            with st.spinner("Testando conexão com Bling..."):
                ok, resp = service.testar_conexao()

                if ok:
                    st.success("Conexão OK com Bling")
                else:
                    st.error(f"Erro: {resp}")

    with col2:
        enviar = st.button("🚀 Enviar para Bling", type="primary")

    # =========================
    # ENVIO
    # =========================
    if enviar:
        if tipo == "estoque" and not deposito_padrao:
            st.error("Informe o depósito antes de enviar.")
            return

        with st.spinner("Enviando dados para o Bling..."):

            ok, resultado = service.enviar_dataframe_completo(
                df=df,
                tipo=tipo,
                deposito_padrao=deposito_padrao,
            )

        if not ok:
            st.error(f"Erro geral: {resultado}")
            return

        # =========================
        # RESULTADO
        # =========================
        st.success("Processo finalizado!")

        st.metric("Total", resultado.get("total", 0))
        st.metric("Sucesso", resultado.get("sucesso", 0))
        st.metric("Erros", resultado.get("erro", 0))

        # =========================
        # LOGS
        # =========================
        with st.expander("📄 Ver logs detalhados"):
            logs = resultado.get("logs", [])

            for log in logs:
                tipo_log = log.get("tipo")

                if tipo_log == "sucesso":
                    st.success(log.get("mensagem"))
                else:
                    st.error(log.get("mensagem"))
                    if log.get("extra"):
                        st.code(str(log.get("extra")))
