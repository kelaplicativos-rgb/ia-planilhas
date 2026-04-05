from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_homologacao import BlingHomologacaoService
from bling_app_zero.core.bling_user_session import (
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    set_current_user,
)
from bling_app_zero.utils.excel import df_to_excel_bytes


def _status_texto(status: dict) -> str:
    if not status.get("connected"):
        return "Desconectado"
    nome = status.get("company_name")
    return f"Conectado{f' • {nome}' if nome else ''}"


def _render_usuario_bling() -> str:
    ensure_current_user_defaults()

    with st.expander("Usuário / operação do Bling", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            identificador = st.text_input(
                "Identificador do usuário",
                value=get_current_user_key(),
                key="bling_user_identifier_input",
                help="Ex.: email, nome da loja ou código interno. Cada identificador mantém um token separado.",
            )
        with c2:
            apelido = st.text_input(
                "Nome exibido",
                value=get_current_user_label(),
                key="bling_user_label_input",
                help="Apenas para facilitar a identificação da operação conectada.",
            )

        if st.button("Usar este usuário", use_container_width=True):
            set_current_user(identificador, apelido)
            st.success("Usuário atual do Bling atualizado.")
            st.rerun()

        st.caption(f"Usuário atual do token: {get_current_user_label()} ({get_current_user_key()})")

    return get_current_user_key()


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")

    user_key = _render_usuario_bling()
    auth = BlingAuthManager(user_key=user_key)
    callback = auth.handle_oauth_callback()

    if callback.get("status") == "success":
        st.success(callback.get("message", "Conta conectada com sucesso."))
    elif callback.get("status") == "error":
        st.error(callback.get("message", "Falha na autenticação com o Bling."))

    status = auth.get_connection_status()
    configurado = auth.is_configured()
    conectar_url = auth.build_authorize_url() if configurado else None

    if not configurado:
        st.warning(
            "Credenciais fixas do app Bling não encontradas no secrets. "
            "Preencha client_id, client_secret e redirect_uri uma vez no ambiente."
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        if conectar_url:
            st.link_button(
                "Conectar com Bling",
                url=conectar_url,
                use_container_width=True,
            )
        else:
            st.button(
                "Conectar com Bling",
                use_container_width=True,
                disabled=True,
            )

    with c2:
        if st.button("Atualizar status", use_container_width=True):
            if status.get("connected"):
                ok, msg = auth.refresh_access_token()
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)
            else:
                st.info("Nenhuma conta conectada no momento.")
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
        st.write(f"Usuário atual: {get_current_user_label()} ({user_key})")
        st.write(f"Status atual: {_status_texto(status)}")
        if status.get("last_auth_at"):
            st.write(f"Última autenticação: {status.get('last_auth_at')}")
        if status.get("expires_at"):
            st.write(f"Expira em: {status.get('expires_at')}")

    if status.get("connected"):
        with st.expander("Homologação do Bling", expanded=False):
            if st.button("Rodar teste de homologação", use_container_width=True):
                service = BlingHomologacaoService(user_key=user_key)
                ok, resultado = service.run()
                st.session_state["bling_homologacao_resultado"] = resultado
                if ok:
                    st.success("Homologação executada.")
                else:
                    st.error("Homologação retornou falhas.")
            resultado = st.session_state.get("bling_homologacao_resultado")
            if isinstance(resultado, dict) and resultado:
                st.json(resultado)


def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    ensure_current_user_defaults()
    user_key = get_current_user_key()
    auth = BlingAuthManager(user_key=user_key)
    status = auth.get_connection_status()

    if not status.get("connected"):
        st.info("Conecte primeiro a conta do Bling para importar produtos e estoque.")
        return

    client = BlingAPIClient(user_key=user_key)

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos do Bling", use_container_width=True):
            ok, payload = client.list_products(page_size=100, max_pages=5)
            if ok:
                df = client.products_to_dataframe(payload)
                st.session_state["bling_produtos_df"] = df
                st.success(f"{len(df)} produto(s) importado(s) do Bling.")
            else:
                st.error(f"Falha ao importar produtos: {payload}")

        df_prod = st.session_state.get("bling_produtos_df")
        if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
            st.dataframe(df_prod, use_container_width=True, height=190)
            st.download_button(
                "Baixar produtos do Bling em Excel",
                data=df_to_excel_bytes(df_prod),
                file_name="produtos_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tab2:
        if st.button("Importar estoque do Bling", use_container_width=True):
            ok, payload = client.list_stocks(page_size=100, max_pages=5)
            if ok:
                df = client.stocks_to_dataframe(payload)
                st.session_state["bling_estoque_df"] = df
                st.success(f"{len(df)} linha(s) de estoque importada(s) do Bling.")
            else:
                st.error(f"Falha ao importar estoque: {payload}")

        df_est = st.session_state.get("bling_estoque_df")
        if isinstance(df_est, pd.DataFrame) and not df_est.empty:
            st.dataframe(df_est, use_container_width=True, height=190)
            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
