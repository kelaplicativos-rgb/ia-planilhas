from __future__ import annotations

import traceback
import pandas as pd
import streamlit as st

# 🔥 IMPORTS CORRETOS
from bling_app_zero.services.bling.bling_auth import BlingAuthManager
from bling_app_zero.services.bling.bling_sync import BlingSync


def _safe_df(df):
    try:
        return isinstance(df, pd.DataFrame) and not df.empty
    except Exception:
        return False


def _safe_str(v):
    try:
        return str(v or "").strip()
    except Exception:
        return ""


def _resolver_user_key():
    try:
        qp_user = st.query_params.get("bi")
        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""
        return _safe_str(qp_user) or "default"
    except Exception:
        return "default"


def _render_conexao(auth: BlingAuthManager):
    callback = auth.handle_oauth_callback()

    if callback.get("status") == "success":
        st.success(callback.get("message"))

    elif callback.get("status") == "error":
        st.error(callback.get("message"))

    if not auth.is_configured():
        st.warning("⚠️ Bling não configurado (verifique st.secrets)")
        return False

    status = auth.get_connection_status()
    conectado = status.get("connected")

    col1, col2 = st.columns(2)

    with col1:
        if conectado:
            st.success("🟢 Conectado ao Bling")
        else:
            st.info("🔴 Não conectado")

    with col2:
        try:
            url = auth.build_authorize_url()
            if url:
                st.link_button("🔗 Conectar com Bling", url, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar URL: {e}")

    return conectado


def render_send_panel():
    st.subheader("🚀 Enviar para Bling")

    df = st.session_state.get("df_final")

    if not _safe_df(df):
        st.warning("⚠️ Nenhum dado disponível para envio.")
        return

    user_key = _resolver_user_key()
    auth = BlingAuthManager(user_key=user_key)
    sync = BlingSync(user_key=user_key)

    conectado = _render_conexao(auth)

    if not conectado:
        st.warning("Conecte ao Bling antes de enviar.")
        return

    tipo = st.radio(
        "Tipo de envio:",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        horizontal=True,
    )

    tipo_api = "cadastro" if tipo == "Cadastro de Produtos" else "estoque"

    deposito_id = None

    if tipo_api == "estoque":
        deposito_id = st.text_input(
            "ID do Depósito",
            placeholder="Ex: 123456",
        )

    st.markdown("---")

    st.info(f"{len(df)} registros prontos para envio")

    if st.button("🚀 Enviar para Bling", use_container_width=True):

        with st.spinner("Enviando dados para o Bling..."):
            try:
                resultado = sync.sync_dataframe(
                    df=df.copy(),
                    tipo=tipo_api,
                    deposito_id=deposito_id,
                )

                total = resultado.get("total", 0)
                sucesso = resultado.get("sucesso", 0)
                erro = resultado.get("erro", 0)

                if resultado.get("ok"):
                    st.success("✅ Envio concluído")
                else:
                    st.error("❌ Falha no envio")

                col1, col2 = st.columns(2)
                col1.metric("Sucesso", sucesso)
                col2.metric("Erros", erro)

                logs = resultado.get("erros", [])

                if logs:
                    with st.expander("📋 Logs detalhados", expanded=(erro > 0)):
                        for item in logs:
                            st.error(str(item))

            except Exception as e:
                st.error(f"Erro crítico: {e}")
                st.text(traceback.format_exc())
