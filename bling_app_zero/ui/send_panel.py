from __future__ import annotations

import hashlib
import traceback

import pandas as pd
import streamlit as st

from bling_app_zero.services.bling.bling_auth import BlingAuthManager
from bling_app_zero.services.bling.bling_sync import BlingSync


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
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


def _normalizar_df_envio(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")
            df[col] = df[col].astype(str).str.replace("⚠️", "", regex=False).str.strip()
        return df
    except Exception:
        return df


# 🔥 CALLBACK AUTOMÁTICO DO BLING
def _processar_callback(auth: BlingAuthManager):
    try:
        query = st.query_params

        code = query.get("code")
        if isinstance(code, list):
            code = code[0]

        error = query.get("error")
        if isinstance(error, list):
            error = error[0]

        if error:
            st.error(f"Erro de autorização do Bling: {error}")
            try:
                st.query_params.clear()
            except Exception:
                pass
            return

        if code:
            with st.spinner("Conectando com Bling..."):
                ok = auth.handle_callback(code)

            if ok:
                st.success("✅ Conectado com sucesso ao Bling!")
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.rerun()
            else:
                st.error("❌ Falha ao conectar com Bling")

    except Exception as e:
        st.error(f"Erro no callback: {e}")


def _obter_df_envio():
    df_final = st.session_state.get("df_final")
    df_saida = st.session_state.get("df_saida")

    if _safe_df(df_final):
        return _normalizar_df_envio(df_final)

    if _safe_df(df_saida):
        try:
            st.session_state["df_final"] = df_saida.copy()
        except Exception:
            st.session_state["df_final"] = df_saida
        return _normalizar_df_envio(df_saida)

    return None


def _hash_df(df: pd.DataFrame, tipo_api: str = "", deposito_id: str = "") -> str:
    try:
        if not _safe_df(df):
            return ""

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

    if "bling_deposito_id" not in st.session_state:
        st.session_state["bling_deposito_id"] = ""


def _render_conexao(auth: BlingAuthManager) -> bool:
    _processar_callback(auth)

    try:
        if not auth.is_configured():
            st.warning("⚠️ Bling não configurado. Verifique as credenciais.")
            return False
    except Exception as e:
        st.error(f"Erro ao validar configuração do Bling: {e}")
        return False

    try:
        status = auth.get_connection_status()
        conectado = bool(status.get("connected"))
    except Exception as e:
        st.error(f"Erro ao verificar conexão com Bling: {e}")
        return False

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
            st.error(f"Erro ao gerar URL: {e}")

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
        with st.expander("📋 Logs detalhados", expanded=True):
            for item in logs:
                st.error(str(item))

    if st.button("🧹 Limpar status do envio", use_container_width=True):
        st.session_state["bling_resultado"] = None
        st.session_state["bling_enviando"] = False
        st.session_state["bling_hash_enviado"] = ""
        st.rerun()


def render_send_panel():
    st.subheader("🚀 Enviar para Bling")

    _garantir_estado()

    df = _obter_df_envio()
    if not _safe_df(df):
        st.warning("⚠️ Nenhum dado disponível para envio.")
        return

    user_key = _resolver_user_key()

    try:
        auth = BlingAuthManager(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar autenticação do Bling: {e}")
        return

    try:
        sync = BlingSync(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar sincronização do Bling: {e}")
        return

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

    with st.expander("📦 Ver dados que serão enviados", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    df_hash = _hash_df(df, tipo_api=tipo_api, deposito_id=deposito_id)

    botao = st.button(
        "🚀 Enviar para Bling",
        use_container_width=True,
        disabled=bool(st.session_state.get("bling_enviando")),
    )

    if botao:
        if st.session_state.get("bling_enviando"):
            st.warning("⚠️ Já existe um envio em andamento.")
            return

        if not df_hash:
            st.error("Não foi possível gerar a assinatura do lote para envio.")
            return

        if st.session_state.get("bling_hash_enviado") == df_hash:
            st.warning("⚠️ Mesmo lote já enviado. Clique em limpar para reenviar.")
            return

        if tipo_api == "estoque" and not _safe_str(deposito_id):
            st.warning("Informe o ID do depósito.")
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
                    "erros": ["Retorno inválido do serviço de sincronização."],
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
