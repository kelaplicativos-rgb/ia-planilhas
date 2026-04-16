
import streamlit as st

from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final

APP_VERSION = "2.0.0"

st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

# =========================
# INICIALIZAÇÃO DE ESTADO
# =========================
if "etapa" not in st.session_state:
    st.session_state.etapa = "origem"

if "df_origem" not in st.session_state:
    st.session_state.df_origem = None

if "df_precificado" not in st.session_state:
    st.session_state.df_precificado = None

if "df_mapeado" not in st.session_state:
    st.session_state.df_mapeado = None

if "df_final" not in st.session_state:
    st.session_state.df_final = None

if "tipo_operacao" not in st.session_state:
    st.session_state.tipo_operacao = "cadastro"

# =========================
# HEADER
# =========================
st.title("🚀 IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

# =========================
# NAVEGAÇÃO
# =========================
etapa = st.session_state.etapa

# =========================
# ETAPAS
# =========================

if etapa == "origem":
    render_origem_dados()

elif etapa == "precificacao":
    render_origem_precificacao()

elif etapa == "mapeamento":
    render_origem_mapeamento()

elif etapa == "final":
    render_preview_final()

# =========================
# DEBUG
# =========================
with st.expander("🧠 DEBUG"):
    st.write("Etapa:", st.session_state.etapa)
    st.write("Tipo operação:", st.session_state.tipo_operacao)
    st.write("DF Origem:", st.session_state.df_origem is not None)
    st.write("DF Precificado:", st.session_state.df_precificado is not None)
    st.write("DF Mapeado:", st.session_state.df_mapeado is not None)
    st.write("DF Final:", st.session_state.df_final is not None)
