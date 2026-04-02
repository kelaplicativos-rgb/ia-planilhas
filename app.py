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
from core.bling import preencher_modelo_estoque, preencher_modelo_cadastro
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

url_base = st.text_input("🌐 Site:", "https://megacentereletronicos.com.br/").strip()

arquivo_dados = st.file_uploader(
    "📄 Planilha de dados",
    type=["xlsx", "xls", "csv"],
    help="Se estiver no celular e o arquivo não aparecer, renomeie para algo simples como dados.csv",
)

modelo_estoque_file = st.file_uploader(
    "📦 Modelo ESTOQUE",
    type=["xlsx", "xls", "csv"],
)

modelo_cadastro_file = st.file_uploader(
    "📋 Modelo CADASTRO",
    type=["xlsx", "xls", "csv"],
)

filtro = st.text_input("🔎 Filtrar produto:", "").strip()

estoque_padrao = st.number_input(
    "📦 Estoque padrão",
    value=10,
    min_value=0,
    step=1,
)

depositos_input = st.text_input(
    "🏬 IDs dos depósitos (separados por vírgula)",
    "14888207145",
)
depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR"):
    logs.clear()

    if not depositos:
        st.error("Informe pelo menos um depósito.")
        st.stop()

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("Envie os dois modelos do Bling: estoque e cadastro.")
        st.stop()

    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.error("Não foi possível ler um dos modelos do Bling.")
        st.stop()

    progress = st.progress(0)

    # =========================
    # PLANILHA
    # =========================
    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("Envie a planilha de dados.")
            st.stop()

        entrada = ler_planilha(arquivo_dados)
        if entrada is None:
            st.error("Não foi possível ler a planilha de dados.")
            st.stop()

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base,
            estoque_padrao,
        )

    # =========================
    # SITE
    # =========================
    df_site = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Site"]:
        links = coletar_links_site(url_base)

        if not links:
            st.error("Nenhum link de produto foi encontrado no site.")
            st.stop()

        st.info(f"🔗 {len(links)} links encontrados no site")

        produtos = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [
                ex.submit(extrair_site, link, filtro, estoque_padrao)
                for link in links
            ]

            total = len(links)
            for i, future in enumerate(as_completed(futures), start=1):
                try:
                    resultado = future.result()
                    if resultado:
                        produtos.append(resultado)
                except Exception as e:
                    logs.append(f"ERRO extrair_site: {e}")

                progress.progress(i / total)

        df_site = pd.DataFrame(produtos)

    # =========================
    # MERGE
    # =========================
    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df.empty:
        st.error("Nenhum dado encontrado após o processamento.")
        st.stop()

    # =========================
    # VALIDAÇÃO FINAL
    # =========================
    for col in ["Código", "Produto", "Preço", "Descrição Curta", "Imagem", "Link", "Marca", "Estoque"]:
        if col not in df.columns:
            df[col] = ""

    df["Código"] = df["Código"].fillna("").astype(str).str.strip()
    df["Produto"] = df["Produto"].fillna("").astype(str).str.strip()
    df["Preço"] = df["Preço"].fillna("0.01").astype(str).str.strip()
    df["Descrição Curta"] = df["Descrição Curta"].fillna("").astype(str).str.strip()
    df["Imagem"] = df["Imagem"].fillna("").astype(str).str.strip()
    df["Link"] = df["Link"].fillna("").astype(str).str.strip()
    df["Marca"] = df["Marca"].fillna("").astype(str).str.strip()

    df = df[df["Produto"] != ""].copy()

    if df.empty:
        st.error("Nenhum produto válido restou após a validação.")
        st.stop()

    # =========================
    # MODELOS BLING
    # =========================
    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    # =========================
    # EXPORTAÇÃO
    # =========================
    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)
    zip_buffer.seek(0)

    st.success("✅ Arquivos prontos.")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "📥 ESTOQUE",
            csv_estoque,
            "estoque.csv",
            mime="text/csv",
        )

    with c2:
        st.download_button(
            "📥 CADASTRO",
            csv_cadastro,
            "cadastro.csv",
            mime="text/csv",
        )

    with c3:
        st.download_button(
            "📦 ZIP",
            zip_buffer.getvalue(),
            "bling.zip",
            mime="application/zip",
        )

    with st.expander("Visualizar base consolidada"):
        st.dataframe(df.head(50))

    with st.expander("Visualizar estoque"):
        st.dataframe(df_estoque.head(50))

    with st.expander("Visualizar cadastro"):
        st.dataframe(df_cadastro.head(50))

# =========================
# LOG
# =========================
if logs:
    st.warning("📄 LOG")
    st.text("\n".join(logs))
