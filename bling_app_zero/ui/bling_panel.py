from __future__ import annotations

import streamlit as st


# ==========================================================
# IMPORTS (PROTEGIDOS)
# ==========================================================
try:
    from bling_app_zero.core.bling_api import BlingAPIClient
except Exception:
    BlingAPIClient = None

try:
    from bling_app_zero.core.bling_auth import BlingAuthManager
except Exception:
    BlingAuthManager = None

try:
    from bling_app_zero.core.bling_user_session import (
        ensure_current_user_defaults,
        get_current_user_key,
        get_current_user_label,
        set_pending_oauth_user,
    )
except Exception:
    ensure_current_user_defaults = None
    get_current_user_key = None
    get_current_user_label = None
    set_pending_oauth_user = None

try:
    from bling_app_zero.ui.bling_panel_helpers import (
        bloquear_importacao,
        bloquear_painel_principal,
        clear_callback_params,
        has_callback_params,
        safe_df,
        status_texto,
    )
except Exception:
    def bloquear_importacao(): return False
    def bloquear_painel_principal(): return False
    def clear_callback_params(): pass
    def has_callback_params(): return False
    def safe_df(x): return x
    def status_texto(x): return str(x)

try:
    from bling_app_zero.ui.bling_panel_usuario import (
        processar_callback_oauth,
        render_usuario_bling,
    )
except Exception:
    def processar_callback_oauth(*args, **kwargs): return False
    def render_usuario_bling(): pass


# ==========================================================
# SAFE SESSION
# ==========================================================
def _safe_session():
    try:
        if not hasattr(st, "session_state"):
            return False
        _ = st.session_state
        return True
    except Exception:
        return False


# ==========================================================
# PAINEL PRINCIPAL
# ==========================================================
def render_bling_panel():

    # 🔥 blindagem crítica
    if not _safe_session():
        st.warning("Sessão ainda não inicializada. Aguarde...")
        return

    if bloquear_painel_principal():
        return

    # 🔥 REMOVIDO: título duplicado (já vem do fluxo principal)

    try:
        render_usuario_bling()
    except Exception as e:
        st.error(f"Erro ao carregar usuário: {e}")
        return

    try:
        if processar_callback_oauth(has_callback_params, clear_callback_params):
            return
    except Exception:
        pass

    try:
        if get_current_user_key is None:
            st.warning("Sistema de usuário não disponível.")
            return

        user_key = get_current_user_key()
        user_label = get_current_user_label()

        if BlingAuthManager is None:
            st.warning("Módulo de autenticação indisponível.")
            return

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
        if set_pending_oauth_user:
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

    if not _safe_session():
        return

    if bloquear_importacao():
        return

    st.markdown("### Importar do Bling")

    try:
        if ensure_current_user_defaults:
            ensure_current_user_defaults()

        if get_current_user_key is None:
            st.warning("Usuário não disponível.")
            return

        user_key = get_current_user_key()

        if BlingAuthManager is None:
            st.warning("Auth indisponível.")
            return

        auth = BlingAuthManager(user_key=user_key)
        ok, msg = auth.get_valid_access_token()

        if not ok:
            st.warning(msg or "Reconecte ao Bling.")
            return

        if BlingAPIClient is None:
            st.warning("API indisponível.")
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
        if hasattr(df_produtos, "empty") and not df_produtos.empty:
            st.dataframe(df_produtos, height=200, use_container_width=True)

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
        if hasattr(df_estoque, "empty") and not df_estoque.empty:
            st.dataframe(df_estoque, height=200, use_container_width=True)
