import io
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st
import urllib3

from core.logger import logs
from core.reader import ler_planilha
from core.scraper import coletar_links_site, extrair_site
from core.normalizer import normalizar_planilha_entrada
from core.bling.estoque import preencher_modelo_estoque
from core.bling.cadastro import preencher_modelo_cadastro
from core.merger import merge_dados

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE PRO", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE PRO")

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
    "📦 Modelo ESTOQUE (Bling)",
    type=["xlsx", "xls", "csv"],
)

modelo_cadastro_file = st.file_uploader(
    "📋 Modelo CADASTRO (Bling)",
    type=["xlsx", "xls", "csv"],
)

estoque_padrao = st.number_input("📦 Estoque padrão", value=10)

depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")
depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR PROCESSAMENTO"):

    logs.clear()

    # =========================
    # VALIDAÇÃO INICIAL
    # =========================
    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling (estoque e cadastro)")
        st.stop()

    if not depositos:
        st.error("❌ Informe pelo menos um depósito")
        st.stop()

    # =========================
    # LEITURA MODELOS
    # =========================
    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.error("❌ Erro ao ler modelos do Bling")
        st.stop()

    progress = st.progress(0)

    # =========================
    # PLANILHA ENTRADA
    # =========================
    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("❌ Envie a planilha de dados")
            st.stop()

        entrada = ler_planilha(arquivo_dados)

        if entrada is None or entrada.empty:
            st.error("❌ Falha ao ler planilha de dados")
            st.stop()

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base,
            estoque_padrao,
        )

        st.success(f"📄 Planilha carregada: {len(df_planilha)} registros")

    # =========================
    # SCRAPER
    # =========================
    df_site = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Site"]:

        st.info("🌐 Coletando links do site...")

        links = coletar_links_site(url_base)

        if not links and modo_coleta == "Só Site":
            st.error("❌ Nenhum produto encontrado no site")
            st.stop()

        produtos = []

        if links:
            st.info(f"🔗 {len(links)} links encontrados")

            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [
                    ex.submit(extrair_site, l, "", estoque_padrao)
                    for l in links
                ]

                total = len(links)

                for i, f in enumerate(as_completed(futures), start=1):
                    try:
                        r = f.result()
                        if r:
                            produtos.append(r)
                    except Exception as e:
                        logs.append(f"ERRO scraper: {e}")

                    progress.progress(i / total)

        df_site = pd.DataFrame(produtos)

        st.success(f"🌐 Produtos coletados do site: {len(df_site)}")

    # =========================
    # MERGE
    # =========================
    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df is None or df.empty:
        st.error("❌ Nenhum dado final gerado")
        st.stop()

    # =========================
    # LIMPEZA FINAL (ANTI ERRO BLING)
    # =========================
    colunas_essenciais = [
        "Código",
        "Produto",
        "Preço",
        "Descrição Curta",
        "Imagem",
        "Link",
        "Marca",
        "Estoque",
    ]

    for col in colunas_essenciais:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")

    df["Código"] = df["Código"].astype(str).str.strip()
    df["Produto"] = df["Produto"].astype(str).str.strip()

    df = df[df["Produto"] != ""].copy()

    if df.empty:
        st.error("❌ Nenhum produto válido após limpeza")
        st.stop()

    st.success(f"📦 Produtos finais: {len(df)}")

    # =========================
    # GERAR BLING
    # =========================
    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    # =========================
    # EXPORT
    # =========================
    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)

    zip_buffer.seek(0)

    # =========================
    # DOWNLOADS
    # =========================
    st.success("✅ Arquivos prontos para importação no Bling")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button("📥 ESTOQUE", csv_estoque, "estoque.csv")

    with col2:
        st.download_button("📥 CADASTRO", csv_cadastro, "cadastro.csv")

    with col3:
        st.download_button("📦 BAIXAR TUDO", zip_buffer.getvalue(), "bling.zip")

# =========================
# LOG + DOWNLOAD
# =========================
if logs:
    st.warning("📄 LOG DEBUG")

    log_texto = "\n".join(logs)

    st.text(log_texto)

    st.download_button(
        label="📥 Baixar LOG (TXT)",
        data=log_texto,
        file_name="debug_log.txt",
        mime="text/plain",
    )
