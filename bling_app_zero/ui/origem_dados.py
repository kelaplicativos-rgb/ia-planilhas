# bling_app_zero/ui/origem_dados.py

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


# =========================
# CONFIG
# =========================

CAMPOS_FIXOS = {
    "condicao": "NOVO",
    "frete_gratis": "NÃO",
    "volume": 1,
    "itens_caixa": 1,
    "unidade_medida": "CENTIMETROS",
    "departamento": "GERAL"
}

COLUNAS_DESTINO = [
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
# UI PRINCIPAL
# =========================

def tela_origem_dados():

    st.title("🤖 Modo Automático Inteligente")

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"]
    )

    if not arquivo:
        return

    # =========================
    # LEITURA
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

    st.success("Arquivo carregado")

    colunas_origem = list(df.columns)

    # =========================
    # IA MAPEAMENTO AUTOMÁTICO
    # =========================

    mapa_ia = mapear_colunas_ia(colunas_origem, COLUNAS_DESTINO)

    mapeamento_auto = {}

    for col, dados in mapa_ia.items():
        destino = dados.get("destino")
        score = dados.get("score", 0)

        # só aceita se confiança alta
        if destino and score >= 0.6:
            mapeamento_auto[col] = destino

    # =========================
    # PREVIEW INTELIGENTE
    # =========================

    st.subheader("⚡ Resultado automático")

    if mapeamento_auto:

        df_preview = pd.DataFrame()

        for origem, destino in mapeamento_auto.items():
            df_preview[destino] = df[origem]

        st.dataframe(df_preview.head(3), use_container_width=True)

        st.success(f"{len(mapeamento_auto)} campos mapeados automaticamente")

    else:
        st.warning("Nenhum mapeamento automático confiável encontrado")

    # =========================
    # BOTÃO GERAR DIRETO
    # =========================

    st.divider()

    if st.button("🚀 Gerar planilha automática"):

        if not mapeamento_auto:
            st.warning("Não foi possível mapear automaticamente")
            return

        df_saida = pd.DataFrame()

        for origem, destino in mapeamento_auto.items():
            df_saida[destino] = df[origem]

        # =========================
        # CAMPOS FIXOS
        # =========================

        for campo, valor in CAMPOS_FIXOS.items():
            df_saida[campo] = valor

        # =========================
        # IA DE PREÇO
        # =========================

        df_saida = calcular_preco_compra_automatico_df(df_saida)

        # =========================
        # DOWNLOAD
        # =========================

        excel_bytes = df_to_excel_bytes(df_saida)

        st.download_button(
            "📥 Baixar planilha pronta",
            data=excel_bytes,
            file_name="bling_importacao_auto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("🔥 Processo 100% automático concluído")
