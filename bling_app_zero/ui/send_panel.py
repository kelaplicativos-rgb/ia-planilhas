from __future__ import annotations

import hashlib
import html
import traceback
from urllib.parse import quote

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
        "bling_primeiro_acesso_decidido": False,
        "bling_primeiro_acesso_escolha": "",
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


def _render_link_mesma_aba(url: str, label: str = "Conectar com Bling") -> None:
    url = _safe_str(url)
    label = _safe_str(label) or "Conectar com Bling"

    if not url:
        st.button(label, disabled=True, use_container_width=True)
        return

    url_html = html.escape(url, quote=True)
    label_html = html.escape(label)

    st.markdown(
        f"""
        <a href="{url_html}" target="_self" style="text-decoration:none;">
            <div style="
                display:flex;
                align-items:center;
                justify-content:center;
                width:100%;
                padding:0.75rem 1rem;
                border-radius:0.5rem;
                background:#ff4b4b;
                color:white;
                font-weight:600;
                text-align:center;
                cursor:pointer;
            ">
                {label_html}
            </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CALLBACK / CONEXÃO
# =========================================================
def _processar_callback(auth: BlingAuthManager) -> None:
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
                st.session_state["bling_primeiro_acesso_decidido"] = True
                st.session_state["bling_primeiro_acesso_escolha"] = "conectar"
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
    except Exception:
        return ""

    return ""


def render_bling_primeiro_acesso(on_skip=None, on_continue=None) -> None:
    _garantir_estado()

    user_key = _resolver_user_key()

    try:
        auth = BlingAuthManager(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar autenticação do Bling: {e}")
        return

    _processar_callback(auth)
    _render_feedback_callback()

    status = _obter_status_conexao(auth)
    conectado = bool(status.get("connected"))

    st.subheader("Conexão com Bling")
    st.write("Deseja conectar com o Bling agora?")

    if conectado:
        st.success("✅ Conta já conectada ao Bling.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Seguir para origem dos dados", use_container_width=True,
