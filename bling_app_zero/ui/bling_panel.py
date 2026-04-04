import pandas as pd
import streamlit as st

from bling_app_zero.utils.excel import df_to_excel_bytes
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import BlingSyncService


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")

    auth = BlingAuthManager()
    status = auth.get_connection_status()

    if not auth.is_configured():
        st.warning(
            "Preencha as credenciais em `.streamlit/secrets.toml` "
            "ou em `App Settings > Secrets` no Streamlit Cloud."
        )
        return

    if status["connected"]:
        st.success("Conta do Bling conectada.")
    else:
        st.info("Conta do Bling ainda não conectada.")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Conectar com Bling", use_container_width=True):
            ok, msg = auth.start_oauth_flow()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with c2:
        if st.button("Atualizar status", use_container_width=True):
            st.rerun()

    with c3:
        if st.button("Desconectar", use_container_width=True):
            ok, msg = auth.disconnect()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    if status["connected"]:
        service = BlingSyncService()

        with st.expander("Teste rápido da conexão", expanded=False):
            if st.button("Testar conexão com a API"):
                ok, payload = service.test_connection()
                if ok:
                    st.success("Conexão OK.")
                    st.json(payload)
                else:
                    st.error(payload)


def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    auth = BlingAuthManager()

    if not auth.is_configured():
        st.info("Configure o Bling para liberar a importação.")
        return

    if not auth.get_connection_status()["connected"]:
        st.info("Conecte sua conta do Bling para importar dados.")
        return

    service = BlingSyncService()
    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        c1, c2 = st.columns([1, 1])

        with c1:
            pagina_produtos = st.number_input(
                "Página de produtos",
                min_value=1,
                value=1,
                step=1,
            )

        with c2:
            limite_produtos = st.number_input(
                "Limite de produtos",
                min_value=1,
                max_value=100,
                value=50,
                step=1,
            )

        if st.button("Puxar produtos do Bling", use_container_width=True):
            ok, payload = service.importar_produtos(
                pagina=int(pagina_produtos),
                limite=int(limite_produtos),
            )
            if ok:
                df = pd.DataFrame(payload)
                st.session_state.bling_produtos_df = df
                st.success(f"{len(df)} produto(s) carregado(s).")
            else:
                st.error(payload)

        df_prod = st.session_state.get("bling_produtos_df")
        if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
            st.dataframe(df_prod, use_container_width=True, height=320)
            st.download_button(
                "Baixar produtos do Bling em Excel",
                data=df_to_excel_bytes(df_prod, "produtos_bling"),
                file_name="produtos_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tab2:
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            pagina_estoque = st.number_input(
                "Página de estoque",
                min_value=1,
                value=1,
                step=1,
            )

        with c2:
            limite_estoque = st.number_input(
                "Limite de estoque",
                min_value=1,
                max_value=100,
                value=50,
                step=1,
            )

        with c3:
            id_deposito = st.text_input("ID depósito (opcional)", value="").strip()

        if st.button("Puxar estoque do Bling", use_container_width=True):
            ok, payload = service.importar_estoques(
                pagina=int(pagina_estoque),
                limite=int(limite_estoque),
                id_deposito=id_deposito or None,
            )
            if ok:
                df = pd.DataFrame(payload)
                st.session_state.bling_estoque_df = df
                st.success(f"{len(df)} registro(s) de estoque carregado(s).")
            else:
                st.error(payload)

        df_est = st.session_state.get("bling_estoque_df")
        if isinstance(df_est, pd.DataFrame) and not df_est.empty:
            st.dataframe(df_est, use_container_width=True, height=320)
            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est, "estoque_bling"),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
