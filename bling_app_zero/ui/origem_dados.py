# bling_app_zero/ui/origem_dados.py

from typing import Dict, List
import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


# =========================
# CONFIG FIXA DO SISTEMA
# =========================

CAMPOS_FIXOS = {
    "condicao": "NOVO",
    "frete_gratis": "NÃO",
    "volume": 1,
    "itens_caixa": 1,
    "unidade_medida": "CENTIMETROS",
    "departamento": "GERAL"
}


# =========================
# FUNÇÃO PRINCIPAL UI
# =========================

def tela_origem_dados():

    st.title("📥 Origem dos Dados")

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"]
    )

    if not arquivo:
        return

    # =========================
    # LEITURA DE ARQUIVO
    # =========================

    try:
        if arquivo.name.endswith(".xml"):
            df = pd.read_xml(arquivo)
        elif arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return

    st.success("Arquivo carregado com sucesso!")

    # =========================
    # PREVIEW
    # =========================

    st.subheader("👀 Preview dos dados")
    st.dataframe(df.head(5), use_container_width=True)

    colunas_origem = list(df.columns)

    # =========================
    # CAMPOS DESTINO (BLING)
    # =========================

    colunas_destino = [
        "nome",
        "preco",
        "custo",
        "sku",
        "gtin",
        "ncm",
        "marca",
        "estoque",
        "categoria",
        "peso"
    ]

    # =========================
    # IA DE MAPEAMENTO
    # =========================

    st.subheader("🧠 Mapeamento Inteligente (IA)")

    mapa_ia = mapear_colunas_ia(colunas_origem, colunas_destino)

    mapeamento_final = {}

    for col in colunas_origem:

        sugestao = mapa_ia.get(col, {})
        destino_sugerido = sugestao.get("destino")
        score = sugestao.get("score", 0)

        col1, col2, col3 = st.columns([3, 3, 1])

        with col1:
            st.write(f"**{col}**")

        with col2:
            escolha = st.selectbox(
                f"Mapear {col}",
                [""] + colunas_destino,
                index=(colunas_destino.index(destino_sugerido) + 1)
                if destino_sugerido in colunas_destino else 0,
                key=f"map_{col}"
            )

        with col3:
            st.write(f"{int(score * 100)}%")

        if escolha:
            mapeamento_final[col] = escolha

    # =========================
    # BOTÃO LIMPAR
    # =========================

    if st.button("🧹 Limpar mapeamento"):
        st.experimental_rerun()

    # =========================
    # GERAÇÃO FINAL
    # =========================

    if st.button("🚀 Gerar planilha final"):

        if not mapeamento_final:
            st.warning("Faça pelo menos um mapeamento")
            return

        df_saida = pd.DataFrame()

        for origem, destino in mapeamento_final.items():
            df_saida[destino] = df[origem]

        # aplicar campos fixos
        for campo, valor in CAMPOS_FIXOS.items():
            df_saida[campo] = valor

        # precificação automática
        df_saida = calcular_preco_compra_automatico_df(df_saida)

        # download
        excel_bytes = df_to_excel_bytes(df_saida)

        st.download_button(
            label="📥 Baixar planilha",
            data=excel_bytes,
            file_name="bling_importacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("Planilha gerada com sucesso!")
