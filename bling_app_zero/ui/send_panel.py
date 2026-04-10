from __future__ import annotations

import hashlib
import traceback

import pandas as pd
import streamlit as st

from bling_app_zero.services.bling.bling_auth import BlingAuthManager
from bling_app_zero.services.bling.bling_sync import BlingSync


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_str(valor) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _resolver_user_key() -> str:
    try:
        qp_user = st.query_params.get("bi")
        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""
        return _safe_str(qp_user) or "default"
    except Exception:
        return "default"


def _obter_df_envio():
    df_final = st.session_state.get("df_final")
    df_saida = st.session_state.get("df_saida")

    if _safe_df(df_final):
        return df_final

    if _safe_df(df_saida):
        try:
            st.session_state["df_final"] = df_saida.copy()
        except Exception:
            st.session_state["df_final"] = df_saida
        return df_saida

    return None


def _hash_df(df: pd.DataFrame, tipo_api: str = "", deposito_id: str = "") -> str:
    try:
        base_hash = hashlib.md5(
            pd.util.hash_pandas_object(df.fillna(""), index=True).values.tobytes()
        ).hexdigest()
        contexto = f"{_safe_str(tipo_api)}|{_safe_str(deposito_id)}"
        return hashlib.md5(f"{base_hash}|{contexto}".encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _garantir_estado():
    if "bling_enviando" not in st.session_state:
        st.session_state["bling_enviando"] = False

    if "bling_hash_enviado" not in st.session_state:
        st.session_state["bling_hash_enviado"] = ""

    if "bling_resultado" not in st.session_state:
        st.session_state["bling_resultado"] = None


def _render_conexao(auth: BlingAuthManager) -> bool:
    callback = auth.handle_oauth_callback()

    if isinstance(callback, dict):
        if callback.get("status") == "success":
            st.success(callback.get("message") or "Conexão com o Bling realizada.")
        elif callback.get("status") == "error":
            st.error(callback.get("message") or "Erro ao conectar com o Bling.")

    if not auth.is_configured():
        st.warning("⚠️ Bling não configurado. Verifique as credenciais em st.secrets.")
        return False

    status = auth.get_connection_status()
    conectado = bool(status.get("connected"))

    col1, col2 = st.columns(2)

    with col1:
        if conectado:
            st.success("✅ Conectado ao Bling")
        else:
            st.info("ℹ️ Não conectado")

    with col2:
        try:
            url = auth.build_authorize_url()
            if url:
                st.link_button("🔗 Conectar com Bling", url, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar URL de conexão: {e}")

    return conectado


def _render_resultado():
    resultado = st.session_state.get("bling_resultado")

    if not isinstance(resultado, dict):
        return

    total = int(resultado.get("total", 0) or 0)
    sucesso = int(resultado.get("sucesso", 0) or 0)
    erro = int(resultado.get("erro", 0) or 0)

    if resultado.get("ok"):
        st.success("✅ Envio concluído")
    else:
        st.error("❌ Falha no envio")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", total)
    col2.metric("Sucesso", sucesso)
    col3.metric("Erros", erro)

    logs = resultado.get("erros", [])
    if logs:
        with st.expander("📋 Logs detalhados", expanded=(erro > 0)):
            for item in logs:
                st.error(str(item))

    if st.button("🧹 Limpar status do envio", use_container_width=True):
        st.session_state["bling_resultado"] = None
        st.session_state["bling_enviando"] = False
        st.rerun()


def render_send_panel():
    st.subheader("🚀 Enviar para Bling")

    _garantir_estado()

    df = _obter_df_envio()
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

    deposito_id = ""
    if tipo_api == "estoque":
        deposito_id = st.text_input(
            "ID do Depósito",
            value=_safe_str(st.session_state.get("bling_deposito_id")),
            placeholder="Ex: 123456",
        )
        st.session_state["bling_deposito_id"] = deposito_id

    st.markdown("---")
    st.info(f"{len(df)} registros prontos para envio")

    df_hash = _hash_df(df, tipo_api=tipo_api, deposito_id=deposito_id)

    botao = st.button(
        "🚀 Enviar para Bling",
        use_container_width=True,
        disabled=bool(st.session_state.get("bling_enviando")),
    )

    if botao:
        if st.session_state.get("bling_enviando"):
            st.warning("⚠️ Já existe um envio em andamento.")
            _render_resultado()
            return

        if st.session_state.get("bling_hash_enviado") == df_hash:
            st.warning("⚠️ Este mesmo lote já foi enviado nesse modo.")
            _render_resultado()
            return

        if tipo_api == "estoque" and not _safe_str(deposito_id):
            st.warning("Informe o ID do depósito antes de enviar.")
            _render_resultado()
            return

        st.session_state["bling_enviando"] = True

        try:
            with st.spinner("Enviando dados para o Bling..."):
                resultado = sync.sync_dataframe(
                    df=df.copy(),
                    tipo=tipo_api,
                    deposito_id=_safe_str(deposito_id) or None,
                )

            if not isinstance(resultado, dict):
                resultado = {
                    "ok": False,
                    "total": len(df),
                    "sucesso": 0,
                    "erro": len(df),
                    "erros": ["Resposta inválida do serviço de sincronização."],
                }

            st.session_state["bling_resultado"] = resultado

            if resultado.get("ok"):
                st.session_state["bling_hash_enviado"] = df_hash

        except Exception as e:
            st.session_state["bling_resultado"] = {
                "ok": False,
                "total": len(df),
                "sucesso": 0,
                "erro": len(df),
                "erros": [str(e), traceback.format_exc()],
            }

        finally:
            st.session_state["bling_enviando"] = False

        st.rerun()

    _render_resultado()
