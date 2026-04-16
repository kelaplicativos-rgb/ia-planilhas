
import streamlit as st
from bling_app_zero.ui.app_helpers import ir_para_etapa
from bling_app_zero.core.pipeline import processar_precificacao


def render_origem_precificacao():
    st.title("💰 Precificação")

    df = st.session_state.get("df_origem")

    if df is None:
        st.warning("Nenhum dado carregado")
        return

    margem = st.number_input("Margem (%)", value=20)

    if st.button("Aplicar Precificação"):
        df_precificado = processar_precificacao(df, margem)
        st.session_state["df_precificado"] = df_precificado
        st.dataframe(df_precificado.head())

    if st.button("Continuar"):
        ir_para_etapa("mapeamento")
