
from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_auth import (
    BlingAuthManager,
    obter_resumo_conexao,
    render_conectar_bling,
)


def _safe_str(value) -> str:
    try:
        return str(value or "").strip()
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


def render_bling_primeiro_acesso(*args, **kwargs) -> None:
    st.markdown("### Conexão com Bling")
    user_key = _resolver_user_key()
    resumo = obter_resumo_conexao(user_key=user_key)

    if bool(resumo.get("conectado")):
        st.success("✅ Conta já conectada ao Bling.")
        if resumo.get("company_name"):
            st.caption(f"Conta: {resumo['company_name']}")
        if resumo.get("expires_at"):
            st.caption(f"Expira em: {resumo['expires_at']}")
    else:
        render_conectar_bling(user_key=user_key, titulo="Conectar conta Bling")


def render_send_panel(*args, **kwargs) -> None:
    st.markdown("### Envio para o Bling")
    user_key = _resolver_user_key()
    auth = BlingAuthManager(user_key=user_key)
    resumo = auth.get_connection_status()

    if not auth.is_configured():
        st.warning("Integração OAuth do Bling ainda não configurada em `.streamlit/secrets.toml`.")
        return

    if not bool(resumo.get("connected")):
        st.info("Conecte sua conta do Bling para liberar o envio.")
        render_conectar_bling(user_key=user_key, titulo="Conectar com Bling")
        return

    st.success("✅ Conexão ativa com o Bling.")
    if resumo.get("company_name"):
        st.caption(f"Conta: {resumo['company_name']}")
    if resumo.get("last_auth_at"):
        st.caption(f"Última autenticação: {resumo['last_auth_at']}")
    if resumo.get("expires_at"):
        st.caption(f"Expira em: {resumo['expires_at']}")

    st.info("O painel de envio pode usar `BlingAPIClient` ou `BlingSync` normalmente, porque o token já ficará disponível pelo OAuth.")
