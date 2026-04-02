import streamlit as st
import urllib3

from core.logger import logs
from ui import render_inputs, executar_fluxo, render_downloads

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE")

params = render_inputs()

if params["executar"]:
    resultado = executar_fluxo(params)
    render_downloads(resultado)

if logs:
    st.warning("📄 LOG")
    st.text("\n".join(logs))
