# bling_app_zero/ui/origem_dados.py

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.memoria_fornecedor import (
    salvar_mapeamento,
    recuperar_mapeamento,
)
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


COLUNAS_DESTINO = [
    "nome", "preco", "custo", "sku", "gtin",
    "ncm", "marca", "estoque", "categoria", "peso"
]


def tela_origem_dados():

    st.title("🤖 IA Automática com Memória")

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"]
    )

    if not arquivo:
        return

    # leitura
    try:
        if arquivo.name.endswith(".xml"):
            df = pd.read_xml(arquivo)
        elif arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler: {e}")
        return

    colunas_origem = list(df.columns)

    # =========================
    # MEMÓRIA PRIMEIRO
    # =========================

    memoria = st.session_state.get("mapeamento_memoria", {})

    mapeamento_memoria = recuperar_mapeamento(memoria, colunas_origem)

    if mapeamento_memoria:
        st.success("⚡ Mapeamento recuperado automaticamente (memória)")
        mapeamento_final = mapeamento_memoria
    else:
        # =========================
        # IA
        # =========================
        mapa_ia = mapear_colunas_ia(colunas_origem, COLUNAS_DESTINO)

        mapeamento_final = {}

        for col, dados in mapa_ia.items():
            if dados.get("destino") and dados.get("score", 0) >= 0.6:
                mapeamento_final[col] = dados["destino"]

    # =========================
    # PREVIEW
    # =========================

    df_preview = pd.DataFrame()

    for origem, destino in mapeamento_final.items():
        df_preview[destino] = df[origem]

    st.dataframe(df_preview.head(3), use_container_width=True)

    # =========================
    # GERAR
    # =========================

    if st.button("🚀 Gerar automático"):

        df_saida = pd.DataFrame()

        for origem, destino in mapeamento_final.items():
            df_saida[destino] = df[origem]

        df_saida = calcular_preco_compra_automatico_df(df_saida)

        # salva memória
        salvar_mapeamento(memoria, colunas_origem, mapeamento_final)
        st.session_state["mapeamento_memoria"] = memoria

        excel_bytes = df_to_excel_bytes(df_saida)

        st.download_button(
            "📥 Baixar",
            data=excel_bytes,
            file_name="bling_auto.xlsx"
        )

        st.success("🔥 Aprendido e gerado automaticamente")
