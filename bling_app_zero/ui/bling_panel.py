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
def _get_etapa_fluxo() -> str:
    try:
        return str(st.session_state.get("etapa_origem", "") or "").strip().lower()
    except Exception:
        return ""


def _bloquear_se_em_fluxo() -> bool:
    """
    Bloqueia os módulos do Bling durante o fluxo principal de origem/mapeamento,
    evitando interferência visual e de estado enquanto o usuário estiver no
    processo de preparação da planilha.
    """
    etapa = _get_etapa_fluxo()

    if etapa in {"mapeamento", "final"}:
        return True

    return False


# ==========================================================
# HELPERS
# ==========================================================
def _status_texto(status: dict) -> str:
    if not isinstance(status, dict) or not status.get("connected"):
        return "Desconectado"

    nome = status.get("company_name")
    return f"Conectado{f' • {nome}' if nome else ''}"


def _has_callback_params() -> bool:
    try:
        return "code" in st.query_params or "error" in st.query_params
    except Exception:
        return False


def _clear_callback_params() -> None:
    try:
        for chave in ["code", "state", "error", "error_description"]:
            if chave in st.query_params:
                del st.query_params[chave]
    except Exception:
        pass


def _safe_df(df):
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def _mensagem_bloqueio():
    st.info("O módulo Bling fica temporariamente oculto durante o mapeamento e a etapa final do fluxo principal.")


# ==========================================================
# USUÁRIO
# ==========================================================
def _render_usuario_bling():
    ensure_current_user_defaults()

    with st.expander("Usuário Bling", expanded=False):
        identificador_atual = get_current_user_key()
        apelido_atual = get_current_user_label()

        identificador = st.text_input(
            "ID do usuário",
            value=identificador_atual,
            key="bling_user_identificador",
        )

        apelido = st.text_input(
            "Nome exibido",
            value=apelido_atual,
            key="bling_user_apelido",
        )

        if st.button("Aplicar usuário", use_container_width=True, key="btn_aplicar_usuario_bling"):
            identificador_limpo = (identificador or "").strip()
            apelido_limpo = (apelido or "").strip()

            if not identificador_limpo:
                st.error("Informe o identificador.")
                return

            set_current_user(
                identificador_limpo,
                apelido_limpo or identificador_limpo,
            )
            st.success("Usuário atualizado.")
            st.rerun()

        st.caption(f"Atual: {get_current_user_label()} ({get_current_user_key()})")


# ==========================================================
# PAINEL PRINCIPAL
# ==========================================================
def render_bling_panel():
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

            auth_callback = BlingAuthManager(user_key=user_key)
            result = auth_callback.handle_oauth_callback()

            if result.get("status") == "success":
                set_current_user(user_key, user_label)
                clear_pending_oauth_user()
                _clear_callback_params()
                st.success("Conectado com sucesso.")
                st.rerun()

            if result.get("status") == "error":
                clear_pending_oauth_user()
                _clear_callback_params()
                st.error(result.get("message", "Erro OAuth"))
                st.rerun()

    except Exception as e:
        st.error(f"Erro OAuth: {e}")
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
                    clear_pending_oauth_user()
                    st.success(msg)
                else:
                    st.error(msg)
            except Exception as e:
                st.error(f"Erro ao desconectar: {e}")
            st.rerun()

    with st.expander("Status da conexão", expanded=False):
        st.write(_status_texto(status))


# ==========================================================
# IMPORTAÇÃO
# ==========================================================
def render_bling_import_panel():
    if _bloquear_se_em_fluxo():
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
                    df = _safe_df(client.products_to_dataframe(payload))
                    st.session_state["bling_produtos_df"] = df.copy()
                    st.success(f"{len(df)} produto(s) importado(s).")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro ao importar produtos: {e}")

        df_produtos = _safe_df(st.session_state.get("bling_produtos_df"))
        if not df_produtos.empty:
            st.dataframe(df_produtos, height=200, width="stretch")

    with tab2:
        if st.button("Importar estoque", key="btn_importar_estoque_bling"):
            try:
                ok, payload = client.list_stocks()
                if ok:
                    df = _safe_df(client.stocks_to_dataframe(payload))
                    st.session_state["bling_estoque_df"] = df.copy()
                    st.success(f"{len(df)} registro(s) importado(s).")
                else:
                    st.error(payload)
            except Exception as e:
                st.error(f"Erro ao importar estoque: {e}")

        df_estoque = _safe_df(st.session_state.get("bling_estoque_df"))
        if not df_estoque.empty:
            st.dataframe(df_estoque, height=200, width="stretch")
