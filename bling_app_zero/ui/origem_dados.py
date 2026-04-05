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

    st.title("📥 Origem dos Dados")

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
    # IA MAPEAMENTO
    # =========================

    mapa_ia = mapear_colunas_ia(colunas_origem, COLUNAS_DESTINO)

    # estado persistente
    if "mapeamento" not in st.session_state:
        st.session_state.mapeamento = {}

    # =========================
    # PREVIEW COMPACTO (MOBILE)
    # =========================

    st.subheader("⚡ Preview inteligente (toque para mapear)")

    df_preview = df.head(1)

    for col in colunas_origem:

        sugestao = mapa_ia.get(col, {})
        destino_sugerido = sugestao.get("destino")
        score = sugestao.get("score", 0)

        valor_preview = str(df_preview[col].iloc[0]) if col in df_preview else ""

        with st.container():

            c1, c2, c3 = st.columns([2, 3, 1])

            # COLUNA ORIGEM
            with c1:
                st.caption("Origem")
                st.write(f"**{col}**")
                st.caption(valor_preview[:40])

            # MAPEAMENTO
            with c2:
                st.caption("Destino")

                escolha = st.selectbox(
                    "",
                    [""] + COLUNAS_DESTINO,
                    index=(COLUNAS_DESTINO.index(destino_sugerido) + 1)
                    if destino_sugerido in COLUNAS_DESTINO else 0,
                    key=f"map_{col}"
                )

                if escolha:
                    st.session_state.mapeamento[col] = escolha

            # SCORE IA
            with c3:
                st.caption("IA")
                st.write(f"{int(score*100)}%")

    # =========================
    # LIMPAR
    # =========================

    if st.button("🧹 Limpar tudo"):
        st.session_state.mapeamento = {}
        st.experimental_rerun()

    # =========================
    # GERAR PLANILHA
    # =========================

    st.divider()

    if st.button("🚀 Gerar planilha automática"):

        if not st.session_state.mapeamento:
            st.warning("Nenhum campo mapeado")
            return

        df_saida = pd.DataFrame()

        for origem, destino in st.session_state.mapeamento.items():
            df_saida[destino] = df[origem]

        # campos fixos
        for campo, valor in CAMPOS_FIXOS.items():
            df_saida[campo] = valor

        # IA preço
        df_saida = calcular_preco_compra_automatico_df(df_saida)

        # download
        excel_bytes = df_to_excel_bytes(df_saida)

        st.download_button(
            "📥 Baixar planilha",
            data=excel_bytes,
            file_name="bling_importacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("Planilha pronta 🔥")
