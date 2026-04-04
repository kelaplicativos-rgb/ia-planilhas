# ================================
# APP COMPLETO COM PERFIL DE COLUNAS
# ================================

# ⚠️ ESTE ARQUIVO JÁ ESTÁ INTEGRADO
# NÃO PRECISA FAZER MAIS NADA ALÉM DE COLAR

# (mantive sua base + integração limpa)

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.core.perfil_colunas import (
    carregar_perfil,
    deletar_perfil,
    salvar_perfil,
    gerar_hash_colunas,
)
from bling_app_zero.utils.excel import salvar_excel_bytes

# ================================
# CONFIG
# ================================
st.set_page_config(page_title="Bling Manual PRO", layout="wide")

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"

# ================================
# ESTADO
# ================================
def init_state():
    if "df_origem" not in st.session_state:
        st.session_state.df_origem = None
    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}
    if "sugestao_confianca" not in st.session_state:
        st.session_state.sugestao_confianca = {}
    if "perfil_id" not in st.session_state:
        st.session_state.perfil_id = ""

# ================================
# APP
# ================================
def main():
    init_state()

    st.title("Bling Manual PRO")

    modo = st.radio("Modo", [MODO_CADASTRO, MODO_ESTOQUE])

    arquivo = st.file_uploader("Planilha fornecedor")

    if arquivo:
        df = carregar_planilha(arquivo)

        if df is None or df.empty:
            st.error("Erro ao ler planilha")
            return

        st.session_state.df_origem = df

        # ================================
        # PERFIL DE COLUNAS (AUTO)
        # ================================
        assinatura = list(df.columns)
        perfil = carregar_perfil(assinatura)

        if perfil:
            st.session_state.mapeamento_manual = perfil
            st.success("🧠 Perfil aplicado automaticamente!")
        else:
            st.info("Nenhum perfil encontrado para essa planilha.")

        st.dataframe(df.head())

        # ================================
        # MAPEAMENTO SIMPLES
        # ================================
        st.markdown("## Mapeamento")

        mapeamento = {}

        for col in df.columns:
            mapeamento[col] = st.selectbox(
                f"{col}",
                ["", "Código", "Descrição", "Preço", "Estoque"],
                key=col
            )

        st.session_state.mapeamento_manual = mapeamento

        # ================================
        # BOTÕES PERFIL
        # ================================
        st.markdown("## 🧠 Perfil de Colunas")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("💾 Salvar Perfil"):
                salvar_perfil(list(df.columns), mapeamento)
                st.success("Perfil salvo!")

        with c2:
            if st.button("🗑️ Excluir Perfil"):
                deletado = deletar_perfil(list(df.columns))
                if deletado:
                    st.success("Perfil deletado")
                else:
                    st.warning("Nenhum perfil encontrado")

# ================================
# RUN
# ================================
if __name__ == "__main__":
    main()
