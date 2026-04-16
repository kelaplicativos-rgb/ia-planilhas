
import streamlit as st
from bling_app_zero.ui.app_helpers import ir_para_etapa
from bling_app_zero.core.pipeline import processar_mapeamento


def render_origem_mapeamento():
    st.title("🔄 Mapeamento")

    df = st.session_state.get("df_precificado")

    if df is None:
        st.warning("Precificação não feita")
        return

    if st.button("Aplicar Mapeamento Automático"):
        df_mapeado = processar_mapeamento(df)
        st.session_state["df_mapeado"] = df_mapeado
        st.dataframe(df_mapeado.head())

    if st.button("Continuar"):
        ir_para_etapa("final")
