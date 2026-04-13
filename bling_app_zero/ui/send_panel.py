from __future__ import annotations

import hashlib
import traceback

import pandas as pd
import streamlit as st

from bling_app_zero.services.bling.bling_auth import BlingAuthManager
from bling_app_zero.services.bling.bling_sync import BlingSync


# =========================================================
# HELPERS
# =========================================================
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


def _garantir_estado() -> None:
    defaults = {
        "bling_enviando": False,
        "bling_hash_enviado": "",
        "bling_resultado": None,
        "bling_deposito_id": "",
        "bling_tipo_envio": "",
        "_bling_oauth_feedback": None,
        "_bling_oauth_processado_local": False,
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


# =========================================================
# CALLBACK / CONEXÃO
# =========================================================
def _processar_callback(auth: BlingAuthManager) -> None:
    """
    Processa o callback OAuth de forma compatível com:
    - auth novo: handle_oauth_callback()
    - auth antigo: handle_callback(code)
    """
    try:
        if not _tem_callback_pendente():
            st.session_state["_bling_oauth_processado_local"] = False
            return

        if st.session_state.get("_bling_oauth_processado_local"):
            return

        st.session_state["_bling_oauth_processado_local"] = True
        resultado = None

        if hasattr(auth, "handle_oauth_callback"):
            resultado = auth.handle_oauth_callback()

        elif hasattr(auth, "handle_callback"):
            code = st.query_params.get("code")
            if isinstance(code, list):
                code = code[0] if code else ""

            code = _safe_str(code)
            if code:
                retorno = auth.handle_callback(code)

                if isinstance(retorno, tuple) and len(retorno) >= 2:
                    ok = bool(retorno[0])
                    msg = _safe_str(retorno[1])
                else:
                    ok = bool(retorno)
                    msg = "Conta Bling conectada com sucesso." if ok else "Falha ao conectar com o Bling."

                resultado = {
                    "status": "success" if ok else "error",
                    "message": msg,
                }

        if not isinstance(resultado, dict):
            return

        status = _safe_str(resultado.get("status")).lower()
        mensagem = _safe_str(resultado.get("message"))

        if status in {"success", "error"}:
            st.session_state["_bling_oauth_feedback"] = {
                "status": status,
                "message": mensagem,
            }

            if status == "success":
                st.rerun()

    except Exception as e:
        st.session_state["_bling_oauth_feedback"] = {
            "status": "error",
            "message": f"Erro no callback do Bling: {e}",
        }


def _render_feedback_callback() -> None:
    feedback = st.session_state.get("_bling_oauth_feedback")
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


def _gerar_url_conexao(auth: BlingAuthManager) -> str:
    try:
        if hasattr(auth, "build_authorize_url"):
            return _safe_str(auth.build_authorize_url())

        if hasattr(auth, "generate_auth_url"):
            return _safe_str(auth.generate_auth_url())
    except Exception:
        return ""

    return ""


def _render_conexao(auth: BlingAuthManager) -> bool:
    _processar_callback(auth)
    _render_feedback_callback()

    try:
        if not auth.is_configured():
            st.warning("⚠️ Bling não configurado. Verifique as credenciais.")
            return False
    except Exception as e:
        st.error(f"Erro ao validar configuração do Bling: {e}")
        return False

    status = _obter_status_conexao(auth)
    conectado = bool(status.get("connected"))

    st.subheader("Integração Bling")

    empresa = _safe_str(status.get("company_name"))
    ultima_auth = _safe_str(status.get("last_auth_at"))
    expira_em = _safe_str(status.get("expires_at"))

    if conectado:
        st.success("✅ Conectado ao Bling")
    else:
        st.info("ℹ️ Não conectado")

    if empresa:
        st.caption(f"Conta: {empresa}")
    if ultima_auth:
        st.caption(f"Última autenticação: {ultima_auth}")
    if expira_em:
        st.caption(f"Expira em: {expira_em}")

    col1, col2 = st.columns(2)

    with col1:
        try:
            url = _gerar_url_conexao(auth)
            if url:
                st.link_button(
                    "Conectar com Bling",
                    url,
                    use_container_width=True,
                )
            else:
                st.button(
                    "Conectar com Bling",
                    disabled=True,
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"Erro ao gerar URL de conexão: {e}")

    with col2:
        if hasattr(auth, "refresh_access_token"):
            if st.button("Atualizar Token", use_container_width=True):
                try:
                    retorno = auth.refresh_access_token()

                    if isinstance(retorno, tuple) and len(retorno) >= 2:
                        ok = bool(retorno[0])
                        msg = _safe_str(retorno[1])
                    else:
                        ok = bool(retorno)
                        msg = "Token atualizado com sucesso." if ok else "Falha ao atualizar token."

                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                except Exception as e:
                    st.error(f"Erro ao atualizar token: {e}")
        else:
            st.button("Atualizar Token", disabled=True, use_container_width=True)

    return conectado


# =========================================================
# RESULTADO
# =========================================================
def _render_resultado() -> None:
    resultado = st.session_state.get("bling_resultado")
    if not isinstance(resultado, dict):
        return

    total = int(resultado.get("total", 0) or 0)
    sucesso = int(resultado.get("sucesso", 0) or 0)
    erro = int(resultado.get("erro", 0) or 0)
    operacao = _safe_str(resultado.get("operacao"))

    if resultado.get("ok"):
        st.success("✅ Envio concluído com sucesso.")
    else:
        st.error("❌ Falha no envio para o Bling.")

    if operacao:
        st.caption(f"Operação: {operacao}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("Sucesso", sucesso)
    with col3:
        st.metric("Erros", erro)

    detalhes = resultado.get("detalhes")
    if isinstance(detalhes, dict) and detalhes:
        deposito_id = _safe_str(detalhes.get("deposito_id"))
        if deposito_id:
            st.caption(f"Depósito usado: {deposito_id}")

    logs = resultado.get("erros", [])
    if isinstance(logs, list) and logs:
        with st.expander("Logs detalhados", expanded=True):
            for item in logs:
                st.error(str(item))

    if st.button("Limpar status do envio", use_container_width=True):
        st.session_state["bling_resultado"] = None
        st.session_state["bling_enviando"] = False
        st.session_state["bling_hash_enviado"] = ""
        st.rerun()


# =========================================================
# ENVIO
# =========================================================
def render_send_panel():
    st.subheader("Enviar para Bling")

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
        st.warning("⚠️ Conecte ao Bling antes de enviar.")
        return

    tipo_atual = _safe_str(st.session_state.get("bling_tipo_envio"))
    opcoes = ["Cadastro de Produtos", "Atualização de Estoque"]
    indice = opcoes.index(tipo_atual) if tipo_atual in opcoes else 0

    tipo = st.radio(
        "Tipo de envio:",
        opcoes,
        horizontal=True,
        index=indice,
    )
    st.session_state["bling_tipo_envio"] = tipo

    tipo_api = "cadastro" if tipo == "Cadastro de Produtos" else "estoque"

    deposito_id = ""
    if tipo_api == "estoque":
        deposito_id = st.text_input(
            "ID do Depósito",
            value=_safe_str(st.session_state.get("bling_deposito_id")),
            placeholder="Ex: 123456",
            help="Obrigatório para atualização de estoque.",
        )
        st.session_state["bling_deposito_id"] = deposito_id

    st.markdown("---")
    st.info(f"{len(df)} registros prontos para envio")

    with st.expander("Ver dados que serão enviados", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    df_hash = _hash_df(df, tipo_api=tipo_api, deposito_id=deposito_id)

    botao = st.button(
        "Enviar para Bling",
        use_container_width=True,
        disabled=bool(st.session_state.get("bling_enviando")),
        type="primary",
    )

    if botao:
        if st.session_state.get("bling_enviando"):
            st.warning("⚠️ Já existe um envio em andamento.")
            return

        if not df_hash:
            st.error("Não foi possível gerar a assinatura do lote para envio.")
            return

        if st.session_state.get("bling_hash_enviado") == df_hash:
            st.warning("⚠️ Esse mesmo lote já foi enviado. Limpe o status para reenviar.")
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
                    "operacao": tipo_api,
                    "total": len(df),
                    "sucesso": 0,
                    "erro": len(df),
                    "erros": ["Retorno inválido do serviço de sincronização."],
                    "detalhes": {
                        "deposito_id": _safe_str(deposito_id) or None,
                    },
                }

            st.session_state["bling_resultado"] = resultado

            if resultado.get("ok"):
                st.session_state["bling_hash_enviado"] = df_hash

        except Exception as e:
            st.session_state["bling_resultado"] = {
                "ok": False,
                "operacao": tipo_api,
                "total": len(df),
                "sucesso": 0,
                "erro": len(df),
                "erros": [str(e), traceback.format_exc()],
                "detalhes": {
                    "deposito_id": _safe_str(deposito_id) or None,
                },
            }
        finally:
            st.session_state["bling_enviando"] = False
            st.rerun()

    _render_resultado()
