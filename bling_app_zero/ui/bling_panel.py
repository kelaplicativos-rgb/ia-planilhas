from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_user_session import (
    clear_pending_oauth_user,
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    get_pending_oauth_user_key,
    get_pending_oauth_user_label,
    set_current_user,
    set_pending_oauth_user,
)


# ==========================================================
# BLOQUEIO DE FLUXO
# ==========================================================
def _bloquear_se_em_fluxo():
    etapa = st.session_state.get("etapa_origem")

    if etapa == "mapeamento":
        # 🔥 PARA TUDO AQUI — NÃO DEIXA PASSAR
        return True

    return False


# ==========================================================
# HELPERS
# ==========================================================
def _status_texto(status: dict) -> str:
    if not status.get("connected"):
        return "Desconectado"
    nome = status.get("company_name")
    return f"Conectado{f' • {nome}' if nome else ''}"


def _has_callback_params() -> bool:
    return "code" in st.query_params or "error" in st.query_params


def _clear_callback_params() -> None:
    try:
        for chave in ["code", "state", "error", "error_description"]:
            if chave in st.query_params:
                del st.query_params[chave]
    except Exception:
        pass


def _safe_df(df):
    if isinstance(df, pd.DataFrame):
        return df
    return pd.DataFrame()


# ==========================================================
# USUÁRIO
# ==========================================================
def _render_usuario_bling():
    ensure_current_user_defaults()

    with st.expander("Usuário Bling", expanded=False):
        identificador = st.text_input(
            "ID do usuário",
            value=get_current_user_key(),
            key="bling_user_identificador",
        )

        apelido = st.text_input(
            "Nome exibido",
            value=get_current_user_label(),
            key="bling_user_apelido",
        )

        if st.button("Aplicar usuário", use_container_width=True):
            if not identificador.strip():
                st.error("Informe o identificador.")
                return

            set_current_user(
                identificador.strip(),
                apelido.strip() or identificador.strip()
            )
            st.success("Usuário atualizado.")
            st.rerun()

        st.caption(
            f"Atual: {get_current_user_label()} ({get_current_user_key()})"
        )


# ==========================================================
# PANEL PRINCIPAL
# ==========================================================
def render_bling_panel():

    # 🔥 BLOQUEIO TOTAL DURANTE MAPEAMENTO
    if _bloquear_se_em_fluxo():
        return

    st.markdown("### Integração com Bling")

    try:
        _render_usuario_bling()
    except Exception as e:
        st.error(f"Erro ao carregar usuário: {e}")
        return

    try:
        if _has_callback_params():
            user_key = get_pending_oauth_user_key() or get_current_user_key()
            user_label = get_pending_oauth_user_label() or get_current_user_label()

            auth = BlingAuthManager(user_key=user_key)
            result = auth.handle_oauth_callback()

            if result.get("status") == "success":
                set_current_user(user_key, user_label)
                clear_pending_oauth_user()
                _clear_callback_params()
                st.success("Conectado com sucesso")
                st.rerun()

            elif result.get("status") == "error":
                clear_pending_oauth_user()
                _clear_callback_params()
                st.error(result.get("message", "Erro OAuth"))
                st.rerun()

    except Exception as e:
        st.error(f"Erro OAuth: {e}")
        return

    try:
        user_key = get_current_user_key()
        auth = BlingAuthManager(user_key=user_key)

        status = auth.get_connection_status()
        configurado = auth.is_configured()

    except Exception as e:
        st.error(f"Erro ao inicializar Bling: {e}")
        return

    if not configurado:
        st.warning("Credenciais do Bling não configuradas.")
        return

    set_pending_oauth_user(user_key, get_current_user_label())

    conectar_url = auth.build_authorize_url(
        force_reauth=bool(status.get("connected"))
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        if conectar_url:
            st.link_button(
                "Conectar com Bling"
                if not status.get("connected")
                else "Reconectar",
                conectar_url,
                use_container_width=True,
            )

    with col2:
        if st.button("Atualizar", use_container_width=True):
            ok, msg = auth.get_valid_access_token()
            if ok:
                st.success("Token OK")
            else:
                st.warning(msg)
            st.rerun()

    with col3:
        if st.button(
            "Desconectar",
            use_container_width=True,
            disabled=not status.get("connected"),
        ):
            ok, msg = auth.disconnect()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()

    with st.expander("Status da conexão"):
        st.write(_status_texto(status))


# ==========================================================
# IMPORTAÇÃO
# ==========================================================
def render_bling_import_panel():

    # 🔥 BLOQUEIO TAMBÉM AQUI
    if _bloquear_se_em_fluxo():
        return

    st.markdown("### Importar do Bling")

    try:
        ensure_current_user_defaults()
        user_key = get_current_user_key()

        auth = BlingAuthManager(user_key=user_key)
        ok, _ = auth.get_valid_access_token()

        if not ok:
            st.warning("Reconecte ao Bling.")
            return

        client = BlingAPIClient(user_key=user_key)

    except Exception as e:
        st.error(f"Erro inicialização: {e}")
        return

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos"):
            ok, payload = client.list_products()
            if ok:
                df = _safe_df(client.products_to_dataframe(payload))
                st.session_state["bling_produtos_df"] = df
                st.success(f"{len(df)} produtos")
            else:
                st.error(payload)

        df = _safe_df(st.session_state.get("bling_produtos_df"))
        if not df.empty:
            st.dataframe(df, height=200, width="stretch")

    with tab2:
        if st.button("Importar estoque"):
            ok, payload = client.list_stocks()
            if ok:
                df = _safe_df(client.stocks_to_dataframe(payload))
                st.session_state["bling_estoque_df"] = df
                st.success(f"{len(df)} registros")
            else:
                st.error(payload)

        df = _safe_df(st.session_state.get("bling_estoque_df"))
        if not df.empty:
            st.dataframe(df, height=200, width="stretch")
