from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_user_session import (
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    set_pending_oauth_user,
)
from bling_app_zero.ui.bling_panel_helpers import (
    bloquear_importacao,
    bloquear_painel_principal,
    clear_callback_params,
    has_callback_params,
    safe_df,
    status_texto,
)
from bling_app_zero.ui.bling_panel_usuario import (
    processar_callback_oauth,
    render_usuario_bling,
)


# ==========================================================
# PAINEL PRINCIPAL
# ==========================================================
def render_bling_panel():
    if bloquear_painel_principal():
        return

    st.markdown("### Integração com Bling")

    try:
        render_usuario_bling()
    except Exception as e:
        st.error(f"Erro ao carregar usuário: {e}")
        return

    if processar_callback_oauth(has_callback_params, clear_callback_params):
        return

    try:
        user_key = get_current_user_key()
        user_label = get_current_user_label()

        auth = BlingAuthManager(user_key=user_key)
        configurado = auth.is_configured()
        status = auth.get_connection_status()

    except Exception as e:
        st.error(f"Erro ao inicializar Bling: {e}")
        return

    if not configurado:
        st.warning("Credenciais do Bling não configuradas.")
        return

    conectar_url = ""
    try:
        set_pending_oauth_user(user_key, user_label)
        conectar_url = auth.build_authorize_url(
            force_reauth=bool(status.get("connected"))
        )
    except Exception as e:
        st.error(f"Erro ao gerar link de conexão: {e}")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        if conectar_url:
            st.link_button(
                "Conectar com Bling" if not status.get("connected") else "Reconectar",
                conectar_url,
                use_container_width=True,
            )
        else:
            st.button(
                "Conectar com Bling",
                use_container_width=True,
                disabled=True,
                key="btn_bling_conectar_desabilitado",
            )

    with col2:
        if st.button("Atualizar", use_container_width=True, key="btn_bling_atualizar"):
            try:
                ok, msg = auth.get_valid_access_token()
                if ok:
                    st.success("Token OK.")
                else:
                    st.warning(msg)
            except Exception as e:
                st.error(f"Erro ao atualizar token: {e}")
            st.rerun()

    with col3:
        if st.button(
            "Desconectar",
            use_container_width=True,
            disabled=not status.get("connected"),
            key="btn_bling_desconectar",
        ):
            try:
                ok, msg = auth.disconnect()
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            except Exception as e:
                st.error(f"Erro ao desconectar: {e}")
            st.rerun()

    with st.expander("Status da conexão", expanded=False):
        st.write(status_texto(status))


# ==========================================================
# IMPORTAÇÃO
# ==========================================================
def render_bling_import_panel():
    if bloquear_importacao():
        return

    st.markdown("### Importar do Bling")

    try:
        ensure_current_user_defaults()
        user_key = get_current_user_key()

        auth = BlingAuthManager(user_key=user_key)
        ok, msg = auth.get_valid_access_token()

        if not ok:
            st.warning(msg or "Reconecte ao Bling.")
            return

        client = BlingAPIClient(user_key=user_key)

    except Exception as e:
        st.error(f"Erro inicialização: {e}")
        return

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos", key="btn_importar_produtos_bling"):
            try:
                ok, payload = client.list_products()
                if ok:
                    df = safe_df(client.products_to_dataframe(payload))
                    st.session_state["bling_produtos_df"] = df.copy()
                    st.success(f"{len(df)} produto(s) importado(s).")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro ao importar produtos: {e}")

        df_produtos = safe_df(st.session_state.get("bling_produtos_df"))
        if not df_produtos.empty:
            st.dataframe(df_produtos, height=200, width="stretch")

    with tab2:
        if st.button("Importar estoque", key="btn_importar_estoque_bling"):
            try:
                ok, payload = client.list_stocks()
                if ok:
                    df = safe_df(client.stocks_to_dataframe(payload))
                    st.session_state["bling_estoque_df"] = df.copy()
                    st.success(f"{len(df)} registro(s) importado(s).")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro ao importar estoque: {e}")

        df_estoque = safe_df(st.session_state.get("bling_estoque_df"))
        if not df_estoque.empty:
            st.dataframe(df_estoque, height=200, width="stretch")
