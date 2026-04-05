import pandas as pd
import streamlit as st

from bling_app_zero.utils.excel import df_to_excel_bytes


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")
    st.info(
        "Esta aba já está separada da raiz.\n\n"
        "Na prioridade do Bling vamos plugar OAuth, refresh automático "
        "e importação/envio real."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.button(
            "Conectar com Bling",
            use_container_width=True,
            disabled=True,
        )

    with c2:
        st.button(
            "Atualizar status",
            use_container_width=True,
            disabled=True,
        )

    with c3:
        st.button(
            "Desconectar",
            use_container_width=True,
            disabled=True,
        )

    with st.expander("Status da conexão", expanded=False):
        st.write("Status atual: módulo ainda em preparação.")


def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Simular produtos do Bling", use_container_width=True):
            df = pd.DataFrame(
                [
                    {"codigo": "BLG-001", "nome": "Produto Bling 1", "preco": 19.90},
                    {"codigo": "BLG-002", "nome": "Produto Bling 2", "preco": 29.90},
                ]
            )
            st.session_state["bling_produtos_df"] = df

        df_prod = st.session_state.get("bling_produtos_df")

        if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
            st.dataframe(
                df_prod,
                use_container_width=True,
                height=190,
            )

            st.download_button(
                "Baixar produtos do Bling em Excel",
                data=df_to_excel_bytes(df_prod),
                file_name="produtos_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tab2:
        if st.button("Simular estoque do Bling", use_container_width=True):
            df = pd.DataFrame(
                [
                    {"codigo": "BLG-001", "estoque": 12, "deposito_id": "1"},
                    {"codigo": "BLG-002", "estoque": 8, "deposito_id": "1"},
                ]
            )
            st.session_state["bling_estoque_df"] = df

        df_est = st.session_state.get("bling_estoque_df")

        if isinstance(df_est, pd.DataFrame) and not df_est.empty:
            st.dataframe(
                df_est,
                use_container_width=True,
                height=190,
            )

            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
