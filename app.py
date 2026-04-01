import streamlit as st
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor

from utils import identificar_colunas_com_ia, gerar_descricao_ia

st.set_page_config(page_title="IA Planilhas Bling PRO", layout="wide")

st.title("🚀 IA Planilhas Bling PRO")

# =========================
# MODO
# =========================
modo = st.radio("Escolha o tipo:", ["📦 Produtos", "📊 Estoque"])

# =========================
# STOP
# =========================
if "stop" not in st.session_state:
    st.session_state.stop = False

def parar():
    st.session_state.stop = True

st.button("🛑 PARAR", on_click=parar)

# =========================
# UPLOAD
# =========================
arquivo = st.file_uploader("Envie sua planilha", type=["csv", "xlsx", "xls"])

if arquivo:

    try:
        # =========================
        # LEITURA INTELIGENTE
        # =========================
        try:
            df = pd.read_csv(arquivo, sep=None, engine='python', on_bad_lines='skip')
        except:
            df = pd.read_excel(arquivo)

        st.success("✅ Planilha carregada")

        # =========================
        # MAPEAMENTO IA
        # =========================
        if modo == "📦 Produtos":
            campos = [
                "nome", "codigo", "preco", "estoque",
                "marca", "categoria", "descricao_curta"
            ]
        else:
            campos = [
                "codigo", "estoque"
            ]

        colunas_mapeadas = identificar_colunas_com_ia(df, campos)

        df_final = pd.DataFrame()

        for destino in campos:
            origem = colunas_mapeadas.get(destino)

            if origem in df.columns:
                df_final[destino] = df[origem]
            else:
                df_final[destino] = ""

        total = len(df_final)

        barra = st.progress(0)
        status = st.empty()

        inicio = time.time()

        # =========================
        # PROCESSAMENTO
        # =========================
        def processar(i):
            if st.session_state.stop:
                return i

            # Só gera descrição se estiver vazia
            if modo == "📦 Produtos":
                if not df_final.loc[i, "descricao_curta"]:
                    nome = df_final.loc[i, "nome"]
                    df_final.loc[i, "descricao_curta"] = gerar_descricao_ia(nome)

            return i

        # =========================
        # PARALELO
        # =========================
        with ThreadPoolExecutor(max_workers=10) as executor:
            for i, _ in enumerate(executor.map(processar, range(total))):

                if st.session_state.stop:
                    st.warning("⛔ Parado")
                    break

                progresso = (i + 1) / total
                barra.progress(progresso)

                tempo_passado = time.time() - inicio
                estimado = (tempo_passado / (i + 1)) * total

                status.text(
                    f"{i+1}/{total} | Tempo restante: {int(estimado - tempo_passado)}s"
                )

        # =========================
        # DOWNLOAD
        # =========================
        nome_arquivo = "bling_produtos.csv" if modo == "📦 Produtos" else "bling_estoque.csv"

        csv = df_final.to_csv(index=False).encode('utf-8')

        st.download_button(
            "📥 Baixar",
            csv,
            nome_arquivo,
            "text/csv"
        )

    except Exception as e:
        st.error(f"Erro: {e}")
