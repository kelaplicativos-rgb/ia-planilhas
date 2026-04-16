
import streamlit as st
from bling_app_zero.core.pipeline import gerar_saida_final


def render_preview_final():
    st.title("📦 Preview Final")

    df = st.session_state.get("df_mapeado")

    if df is None:
        st.warning("Nada para exibir")
        return

    df_final = gerar_saida_final(df)
    st.session_state["df_final"] = df_final

    st.dataframe(df_final.head())

    csv = df_final.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="bling_import.csv",
        mime="text/csv",
    )
