import streamlit as st
import pandas as pd
import time
import os
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="🔥 IA Planilhas Bling PRO", layout="wide")

st.title("🔥 IA Planilhas Bling PRO")

# =========================
# CONTROLE STOP
# =========================
if "stop" not in st.session_state:
    st.session_state.stop = False

def stop_process():
    st.session_state.stop = True

st.button("🛑 PARAR PROCESSAMENTO", on_click=stop_process)

# =========================
# FUNÇÕES BASE
# =========================

def normalizar(col):
    return str(col).lower().strip().replace(" ", "_")

def detectar_colunas(df):
    mapa = {}

    for col in df.columns:
        c = normalizar(col)

        if "nome" in c:
            mapa["nome"] = col
        elif "sku" in c or "codigo" in c:
            mapa["codigo"] = col
        elif "preco" in c:
            mapa["preco"] = col
        elif "estoque" in c:
            mapa["estoque"] = col
        elif "marca" in c:
            mapa["marca"] = col
        elif "categoria" in c:
            mapa["categoria"] = col
        elif "descricao" in c:
            mapa["descricao_curta"] = col

    return mapa

def carregar_modelo():
    caminho = "modelos/modelo_produtos.csv"
    return pd.read_csv(caminho)

def montar_saida(df, mapa, modelo):
    resultado = pd.DataFrame(columns=modelo.columns)

    for i in range(len(df)):
        if st.session_state.stop:
            break

        linha = {}

        for col_modelo in modelo.columns:
            if col_modelo in mapa:
                linha[col_modelo] = df.loc[i, mapa[col_modelo]]
            else:
                linha[col_modelo] = ""

        resultado.loc[i] = linha

    return resultado

# =========================
# UPLOAD
# =========================

arquivo = st.file_uploader("📂 Envie sua planilha", type=["csv", "xlsx", "xls"])

if arquivo:

    inicio = time.time()

    try:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)

        st.success("✅ Planilha carregada")

        modelo = carregar_modelo()

        mapa = detectar_colunas(df)

        st.write("🧠 Mapeamento detectado:", mapa)

        progress = st.progress(0)
        status = st.empty()

        total = len(df)

        resultado = pd.DataFrame(columns=modelo.columns)

        for i in range(total):

            if st.session_state.stop:
                st.warning("⛔ Processo interrompido")
                break

            linha = {}

            for col_modelo in modelo.columns:
                if col_modelo in mapa:
                    valor = df.loc[i, mapa[col_modelo]]

                    # regra: descrição só se existir
                    if col_modelo == "descricao_curta":
                        if pd.isna(valor) or str(valor).strip() == "":
                            valor = ""
                    
                    linha[col_modelo] = valor
                else:
                    linha[col_modelo] = ""

            resultado.loc[i] = linha

            progresso = int((i + 1) / total * 100)
            progress.progress(progresso)

            tempo_decorrido = time.time() - inicio
            estimativa = (tempo_decorrido / (i+1)) * total

            status.write(f"📊 {progresso}% | ⏱ {int(estimativa - tempo_decorrido)}s restantes")

        st.success("🚀 Processamento finalizado")

        st.download_button(
            "⬇️ Baixar planilha Bling",
            resultado.to_csv(index=False).encode("utf-8"),
            file_name="bling_import.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error("❌ Erro no processamento")
        st.code(str(e))
