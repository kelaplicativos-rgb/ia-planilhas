
import streamlit as st


def ir_para_etapa(etapa):
    st.session_state["etapa"] = etapa
    st.rerun()


def get_etapa():
    return st.session_state.get("etapa", "origem")
