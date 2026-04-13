from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.services.bling.bling_auth import BlingAuthManager
from bling_app_zero.services.bling.bling_sync import BlingSync


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(value) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _resolver_user_key() -> str:
    try:
        qp_user = st.query_params.get("bi")
        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""
        return _safe_str(qp_user) or "default"
    except Exception:
        return "default"


def _garantir_estado_local() -> None:
    defaults = {
        "_bling_panel_feedback": None,
        "_bling_panel_processado_local": False,
        "bling_panel_deposito_id": "",
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _tem_callback_pendente() -> bool:
    try:
        qp = st.query_params
        return any(chave in qp for chave in ("code", "state", "error", "error_description"))
    except Exception:
        return False


def _processar_callback(auth: BlingAuthManager) -> None:
    try:
        if not _tem_callback_pendente():
            st.session_state["_bling_panel_processado_local"] = False
            return

        if st.session_state.get("_bling_panel_processado_local"):
            return

        st.session_state["_bling_panel_processado_local"] = True

        if not hasattr(auth, "handle_oauth_callback"):
            return

        resultado = auth.handle_oauth_callback()
        if not isinstance(resultado, dict):
            return

        status = _safe_str(resultado.get("status")).lower()
        mensagem = _safe_str(resultado.get("message"))

        if status in {"success", "error"}:
            st.session_state["_bling_panel_feedback"] = {
                "status": status,
                "message": mensagem,
            }

            if status == "success":
                st.rerun()

    except Exception as e:
        st.session_state["_bling_panel_feedback"] = {
            "status": "error",
            "message": f"Erro no callback do Bling: {e}",
        }


def _render_feedback() -> None:
    feedback = st.session_state.get("_bling_panel_feedback")
    if not isinstance(feedback, dict):
        return

    status = _safe_str(feedback.get("status")).lower()
    mensagem = _safe_str(feedback.get("message"))

    if status == "success" and mensagem:
        st.success(f"✅ {mensagem}")
    elif status == "error" and mensagem:
        st.error(f"❌ {mensagem}")


def _obter_status_conexao(auth: BlingAuthManager) -> dict:
    try:
        status = auth.get_connection_status()
        if isinstance(status, dict):
            return status
    except Exception:
        pass

    return {
        "connected": False,
        "company_name": None,
        "last_auth_at": None,
        "expires_at": None,
    }


def _obter_df_para_envio():
    for key in ["df_final", "df_saida", "df_resultado_final", "df_precificado", "df_origem"]:
        df = st.session_state.get(key)
        if _safe_df(df):
            return df.copy()
    return None


# ==========================================================
# PAINEL PRINCIPAL
# ==========================================================
def render_bling_panel() -> None:
    _garantir_estado_local()

    user_key = _resolver_user_key()

    try:
        auth = BlingAuthManager(user_key=user_key)
    except Exception as e:
        st.warning(f"Painel do Bling indisponível: {e}")
        return

    _processar_callback(auth)
    _render_feedback()

    if not auth.is_configured():
        st.info("Integração com Bling ainda não configurada.")
        return

    status = _obter_status_conexao(auth)
    conectado = bool(status.get("connected"))

    st.markdown("### Integração Bling")

    empresa = _safe_str(status.get("company_name"))
    ultima_auth = _safe_str(status.get("last_auth_at"))
    expira_em = _safe_str(status.get("expires_at"))

    if conectado:
        st.success("✅ Conectado ao Bling")
    else:
        st.info("ℹ️ Não conectado ao Bling")

    if empresa:
        st.caption(f"Conta: {empresa}")
    if ultima_auth:
        st.caption(f"Última autenticação: {ultima_auth}")
    if expira_em:
        st.caption(f"Expira em: {expira_em}")

    st.caption("A conexão principal agora acontece no início do fluxo.")
    st.markdown("---")

    df_envio = _obter_df_para_envio()
    if not _safe_df(df_envio):
        st.info("Nenhum dado disponível para envio/importação neste momento.")
        return

    if not conectado:
        st.warning("Conecte ao Bling no início do fluxo para liberar o envio.")
        return

    tipo = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    if tipo not in {"cadastro", "estoque"}:
        st.info("Selecione o tipo de operação para liberar o envio.")
        return

    try:
        sync = BlingSync(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar sincronização do Bling: {e}")
        return

    deposito_id = ""
    if tipo == "estoque":
        deposito_id = st.text_input(
            "ID do depósito",
            value=_safe_str(st.session_state.get("bling_panel_deposito_id")),
            placeholder="Ex.: 123456",
            key="bling_panel_deposito_id",
        )

    with st.expander("Prévia de dados do painel Bling", expanded=False):
        st.dataframe(df_envio.head(20), use_container_width=True)

    label_botao = (
        "Enviar produtos pelo painel Bling"
        if tipo == "cadastro"
        else "Enviar estoque pelo painel Bling"
    )

    if st.button(label_botao, use_container_width=True):
        if tipo == "estoque" and not _safe_str(deposito_id):
            st.warning("Informe o ID do depósito.")
            return

        try:
            with st.spinner("Enviando dados para o Bling..."):
                resultado = sync.sync_dataframe(
                    df=df_envio.copy(),
                    tipo=tipo,
                    deposito_id=_safe_str(deposito_id) or None,
                )

            if not isinstance(resultado, dict):
                st.error("Retorno inválido do envio para Bling.")
                return

            if resultado.get("ok"):
                st.success("✅ Envio concluído com sucesso.")
            else:
                st.error("❌ Falha no envio para o Bling.")

            total = int(resultado.get("total", 0) or 0)
            sucesso = int(resultado.get("sucesso", 0) or 0)
            erro = int(resultado.get("erro", 0) or 0)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total", total)
            with col2:
                st.metric("Sucesso", sucesso)
            with col3:
                st.metric("Erros", erro)

            erros = resultado.get("erros", [])
            if isinstance(erros, list) and erros:
                with st.expander("Logs do painel Bling", expanded=True):
                    for item in erros:
                        st.error(str(item))

        except Exception as e:
            st.error(f"Erro ao enviar pelo painel Bling: {e}")


# ==========================================================
# IMPORT PANEL
# ==========================================================
def render_bling_import_panel() -> None:
    st.markdown("### Importar do Bling")
    st.info("Painel de importação temporariamente simplificado até a estabilização da integração.")
