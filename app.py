import io
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st
import urllib3

from core.logger import logs, log
from core.reader import ler_planilha
from core.scraper import coletar_links_site, extrair_site
from core.normalizer import normalizar_planilha_entrada
from core.bling_models import preencher_modelo_estoque, preencher_modelo_cadastro
from core.merger import merge_dados

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE")

# =========================
# INPUTS
# =========================
modo_coleta = st.radio(
    "📥 Fonte dos dados",
    ["Planilha + Site", "Só Planilha", "Só Site"],
    horizontal=True,
)

url_base = st.text_input("🌐 Site:", "https://megacentereletronicos.com.br/")

arquivo_dados = st.file_uploader(
    "📄 Planilha de dados",
    type=["xlsx", "xls", "csv"],
)

modelo_estoque_file = st.file_uploader(
    "📦 Modelo ESTOQUE",
    type=["xlsx", "xls", "csv"],
)

modelo_cadastro_file = st.file_uploader(
    "📋 Modelo CADASTRO",
    type=["xlsx", "xls", "csv"],
)

estoque_padrao = st.number_input("📦 Estoque padrão", value=10)

depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")
depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR"):
    logs.clear()

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("Envie os modelos do Bling")
        st.stop()

    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.stop()

    progress = st.progress(0)

    df_planilha = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("Envie a planilha de dados")
            st.stop()

        entrada = ler_planilha(arquivo_dados)
        df_planilha = normalizar_planilha_entrada(
            entrada, url_base, estoque_padrao
        )

    df_site = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Site"]:
        links = coletar_links_site(url_base)

        produtos = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [
                ex.submit(extrair_site, l, "", estoque_padrao)
                for l in links
            ]

            for i, f in enumerate(as_completed(futures)):
                r = f.result()
                if r:
                    produtos.append(r)

                progress.progress((i + 1) / len(links))

        df_site = pd.DataFrame(produtos)

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df.empty:
        st.error("Nenhum dado encontrado")
        st.stop()

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)

    st.success("Arquivos prontos")

    st.download_button("📥 ESTOQUE", csv_estoque, "estoque.csv")
    st.download_button("📥 CADASTRO", csv_cadastro, "cadastro.csv")
    st.download_button("📦 ZIP", zip_buffer.getvalue(), "bling.zip")

# =========================
# LOG
# =========================
if logs:
    st.warning("LOG")
    st.text("\n".join(logs))
