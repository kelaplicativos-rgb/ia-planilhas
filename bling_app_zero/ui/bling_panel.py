from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_homologacao import BlingHomologacaoService
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
from bling_app_zero.utils.excel import df_to_excel_bytes


def _status_texto(status: dict) -> str:
    if not status.get("connected"):
        return "Desconectado"
    nome = status.get("company_name")
    return f"Conectado{f' • {nome}' if nome else ''}"


def _has_callback_params() -> bool:
    return "code" in st.query_params or "error" in st.query_params


def _coerce_dataframe(df) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def _render_usuario_bling() -> str:
    ensure_current_user_defaults()

    with st.expander("Usuário / operação do Bling", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            identificador = st.text_input(
                "Identificador do usuário",
                value=get_current_user_key(),
                key="bling_user_identifier_input",
            )

        with c2:
            apelido = st.text_input(
                "Nome exibido",
                value=get_current_user_label(),
                key="bling_user_label_input",
            )

        if st.button("Usar este usuário", use_container_width=True):
            identificador_limpo = str(identificador or "").strip()
            apelido_limpo = str(apelido or "").strip()

            if not identificador_limpo:
                st.error("Informe o identificador do usuário.")
            else:
                if not apelido_limpo:
                    apelido_limpo = identificador_limpo
                set_current_user(identificador_limpo, apelido_limpo)
                st.success("Usuário atualizado.")
                st.rerun()

        st.caption(
            f"Usuário atual: {get_current_user_label()} ({get_current_user_key()})"
        )

    return get_current_user_key()


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")

    _render_usuario_bling()

    # 🔒 CALLBACK CONTROLADO
    if _has_callback_params():
        callback_user_key = get_pending_oauth_user_key()
        callback_user_label = get_pending_oauth_user_label()

        callback_auth = BlingAuthManager(user_key=callback_user_key)
        callback = callback_auth.handle_oauth_callback()

        if callback.get("status") == "success":
            set_current_user(callback_user_key, callback_user_label)
            clear_pending_oauth_user()
            st.success(callback.get("message", "Conta conectada com sucesso."))
        elif callback.get("status") == "error":
            clear_pending_oauth_user()
            st.error(callback.get("message", "Falha na autenticação com o Bling."))

    user_key = get_current_user_key()
    user_label = get_current_user_label()

    auth = BlingAuthManager(user_key=user_key)
    status = auth.get_connection_status()
    configurado = auth.is_configured()

    if not configurado:
        st.warning(auth.get_missing_config_message())
        return

    set_pending_oauth_user(user_key, user_label)
    conectar_url = auth.build_authorize_url(force_reauth=bool(status.get("connected")))

    c1, c2, c3 = st.columns(3)

    with c1:
        if conectar_url:
            st.link_button(
                "Conectar com Bling"
                if not status.get("connected")
                else "Reconectar com Bling",
                url=conectar_url,
                use_container_width=True,
            )

    with c2:
        if st.button("Atualizar status", use_container_width=True):
            ok, msg = auth.get_valid_access_token()
            if ok:
                st.success("Token válido.")
            else:
                st.warning(msg)
            st.rerun()

    with c3:
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

    with st.expander("Status da conexão", expanded=False):
        st.write(f"Usuário: {user_label}")
        st.write(f"Status: {_status_texto(status)}")


def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    ensure_current_user_defaults()
    user_key = get_current_user_key()
    auth = BlingAuthManager(user_key=user_key)

    ok_token, msg = auth.get_valid_access_token()

    if not ok_token:
        st.warning("Token inválido ou expirado. Reconecte ao Bling.")
        return

    client = BlingAPIClient(user_key=user_key)

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos", use_container_width=True):
            try:
                ok, payload = client.list_products(page_size=100, max_pages=5)
                if ok:
                    df = _coerce_dataframe(client.products_to_dataframe(payload))
                    st.session_state["bling_produtos_df"] = df
                    st.success(f"{len(df)} produtos importados.")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro: {e}")

        df_prod = _coerce_dataframe(st.session_state.get("bling_produtos_df"))
        if not df_prod.empty:
            st.dataframe(df_prod, use_container_width=True, height=190)

    with tab2:
        if st.button("Importar estoque", use_container_width=True):
            try:
                ok, payload = client.list_stocks(page_size=100, max_pages=5)
                if ok:
                    df = _coerce_dataframe(client.stocks_to_dataframe(payload))
                    st.session_state["bling_estoque_df"] = df
                    st.success(f"{len(df)} registros de estoque.")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro: {e}")

        df_est = _coerce_dataframe(st.session_state.get("bling_estoque_df"))
        if not df_est.empty:
            st.dataframe(df_est, use_container_width=True, height=190)
