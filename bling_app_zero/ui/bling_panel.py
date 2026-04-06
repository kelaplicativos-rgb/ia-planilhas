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
                help=(
                    "Ex.: email, nome da loja ou código interno. "
                    "Cada identificador mantém um token separado."
                ),
            )

        with c2:
            apelido = st.text_input(
                "Nome exibido",
                value=get_current_user_label(),
                key="bling_user_label_input",
                help="Apenas para facilitar a identificação da operação conectada.",
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
                st.success("Usuário atual do Bling atualizado.")
                st.rerun()

        st.caption(
            f"Usuário atual do token: {get_current_user_label()} ({get_current_user_key()})"
        )

    return get_current_user_key()


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")

    _render_usuario_bling()

    callback_user_key = (
        get_pending_oauth_user_key() if _has_callback_params() else get_current_user_key()
    )
    callback_user_label = (
        get_pending_oauth_user_label()
        if _has_callback_params()
        else get_current_user_label()
    )

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

        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("Conectar com Bling", use_container_width=True, disabled=True)
        with c2:
            st.button("Atualizar status", use_container_width=True, disabled=True)
        with c3:
            st.button("Desconectar", use_container_width=True, disabled=True)
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
        else:
            st.button("Conectar com Bling", use_container_width=True, disabled=True)

    with c2:
        if st.button("Atualizar status", use_container_width=True):
            if status.get("connected"):
                ok, msg = auth.get_valid_access_token()
                if ok:
                    st.success("Status atualizado com sucesso.")
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
        st.write(f"Usuário atual: {user_label} ({user_key})")
        st.write(f"Status atual: {_status_texto(status)}")
        if status.get("last_auth_at"):
            st.write(f"Última autenticação: {status.get('last_auth_at')}")
        if status.get("expires_at"):
            st.write(f"Expira em: {status.get('expires_at')}")

    if status.get("connected"):
        with st.expander("Homologação do Bling", expanded=False):
            if st.button("Rodar teste de homologação", use_container_width=True):
                progresso = st.progress(0, text="Preparando homologação...")
                try:
                    progresso.progress(30, text="Conectando ao Bling...")
                    service = BlingHomologacaoService(user_key=user_key)
                    progresso.progress(70, text="Executando testes...")
                    ok, resultado = service.run()
                    st.session_state["bling_homologacao_resultado"] = resultado
                    progresso.progress(100, text="Homologação concluída")
                    if ok:
                        st.success("Homologação executada.")
                    else:
                        st.error("Homologação retornou falhas.")
                except Exception as e:
                    progresso.progress(100, text="Erro na homologação")
                    st.error(f"Erro ao rodar homologação: {e}")

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
            progresso = st.progress(0, text="Preparando importação de produtos...")
            try:
                progresso.progress(25, text="Conectando ao Bling...")
                ok, payload = client.list_products(page_size=100, max_pages=5)
                progresso.progress(70, text="Transformando produtos em planilha...")

                if ok:
                    df = _coerce_dataframe(client.products_to_dataframe(payload))
                    st.session_state["bling_produtos_df"] = df
                    progresso.progress(100, text="Importação de produtos concluída")
                    st.success(f"{len(df)} produto(s) importado(s) do Bling.")
                else:
                    progresso.progress(100, text="Falha na importação de produtos")
                    st.error(f"Falha ao importar produtos: {payload}")
            except Exception as e:
                progresso.progress(100, text="Erro na importação de produtos")
                st.error(f"Erro ao importar produtos do Bling: {e}")

        df_prod = _coerce_dataframe(st.session_state.get("bling_produtos_df"))
        if not df_prod.empty:
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
            progresso = st.progress(0, text="Preparando importação de estoque...")
            try:
                progresso.progress(25, text="Conectando ao Bling...")
                ok, payload = client.list_stocks(page_size=100, max_pages=5)
                progresso.progress(70, text="Transformando estoque em planilha...")

                if ok:
                    df = _coerce_dataframe(client.stocks_to_dataframe(payload))
                    st.session_state["bling_estoque_df"] = df
                    progresso.progress(100, text="Importação de estoque concluída")
                    st.success(f"{len(df)} linha(s) de estoque importada(s) do Bling.")
                else:
                    progresso.progress(100, text="Falha na importação de estoque")
                    st.error(f"Falha ao importar estoque: {payload}")
            except Exception as e:
                progresso.progress(100, text="Erro na importação de estoque")
                st.error(f"Erro ao importar estoque do Bling: {e}")

        df_est = _coerce_dataframe(st.session_state.get("bling_estoque_df"))
        if not df_est.empty:
            st.dataframe(df_est, use_container_width=True, height=190)
            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
