import re
import unicodedata

import pandas as pd
import streamlit as st

from core.leitor import carregar_planilha
from core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
)
from core.validacao_bling import (
    validar_cadastro_bling,
    validar_estoque_bling,
)
from utils.excel import (
    ler_planilha,
    salvar_excel_bytes,
    salvar_txt_bytes,
    bloco_toggle,
)


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Bling Automação PRO", layout="wide")


# =========================================================
# ESTADO
# =========================================================
def init_state() -> None:
    defaults = {
        "logs": [],
        "df_origem": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "nome_modelo_cadastro": "",
        "nome_modelo_estoque": "",
        "modelo_cadastro_raw": None,
        "modelo_estoque_raw": None,
        "mapa_manual": {},
        "ultimo_tipo_processamento": "Cadastro de produtos",
        "ultima_chave_arquivo": "",
        "validacao_erros": [],
        "validacao_avisos": [],
        "validacao_ok": False,
        "ultimo_mapeamento_auto": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str) -> None:
    st.session_state.logs.append(str(msg))


def resetar_validacao() -> None:
    st.session_state["validacao_erros"] = []
    st.session_state["validacao_avisos"] = []
    st.session_state["validacao_ok"] = False


def limpar_tudo() -> None:
    chaves_base = {
        "logs": [],
        "df_origem": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "nome_modelo_cadastro": "",
        "nome_modelo_estoque": "",
        "modelo_cadastro_raw": None,
        "modelo_estoque_raw": None,
        "mapa_manual": {},
        "ultimo_tipo_processamento": "Cadastro de produtos",
        "ultima_chave_arquivo": "",
        "validacao_erros": [],
        "validacao_avisos": [],
        "validacao_ok": False,
        "ultimo_mapeamento_auto": {},
    }

    for chave, valor in chaves_base.items():
        st.session_state[chave] = valor

    for chave in list(st.session_state.keys()):
        if chave.startswith("map_"):
            del st.session_state[chave]


# =========================================================
# HELPERS GERAIS
# =========================================================
def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return str(valor).strip()


def normalizar_texto(texto: str) -> str:
    texto = limpar_texto(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("/", " ")
    texto = texto.replace("\\", " ")
    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")
   
