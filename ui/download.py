import streamlit as st


def render_downloads(resultado):
    if not resultado:
        return

    st.success("✅ Arquivos prontos.")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "📥 ESTOQUE",
            resultado["csv_estoque"],
            "estoque.csv",
            mime="text/csv",
        )

    with c2:
        st.download_button(
            "📥 CADASTRO",
            resultado["csv_cadastro"],
            "cadastro.csv",
            mime="text/csv",
        )

    with c3:
        st.download_button(
            "📦 ZIP",
            resultado["zip_bytes"],
            "bling.zip",
            mime="application/zip",
        )

    with st.expander("Visualizar base consolidada"):
        st.dataframe(resultado["df"].head(50))

    with st.expander("Visualizar estoque"):
        st.dataframe(resultado["df_estoque"].head(50))

    with st.expander("Visualizar cadastro"):
        st.dataframe(resultado["df_cadastro"].head(50))
