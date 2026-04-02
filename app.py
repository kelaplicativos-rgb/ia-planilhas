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
from core.bling.estoque import preencher_modelo_estoque
from core.bling.cadastro import preencher_modelo_cadastro
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

estoque_padrao = st.number_input("📦 Estoque padrão", value=10, min_value=0)

depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")
depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR"):
    logs.clear()
    log("🔥 EXECUTANDO FLUXO 🔥")

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("Envie os modelos do Bling")
        st.stop()

    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.error("Erro ao ler os modelos do Bling")
        st.stop()

    progress = st.progress(0)

    # =========================
    # PLANILHA
    # =========================
    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        log("Modo com planilha ativado")

        if not arquivo_dados:
            st.error("Envie a planilha de dados")
            st.stop()

        entrada = ler_planilha(arquivo_dados)

        if entrada is None:
            st.error("Erro ao ler planilha")
            st.stop()

        log(f"Planilha de entrada lida com {len(entrada)} linhas")

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base,
            estoque_padrao,
        )

        log(f"Planilha normalizada com {len(df_planilha)} linhas")

    # =========================
    # SITE
    # =========================
    df_site = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Site"]:
        log("Modo com site ativado")

        links = coletar_links_site(url_base)
        log(f"Total de links retornados pela coleta: {len(links)}")

        produtos = []

        if links:
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
                        log(f"Erro scraper: {e}")

                    progress.progress(i / total)

        df_site = pd.DataFrame(produtos)
        log(f"Produtos extraídos do site: {len(df_site)}")

    # =========================
    # MERGE
    # =========================
    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df is None or df.empty:
        st.error("Nenhum dado encontrado")
        log("Nenhum dado encontrado após merge")
        st.stop()

    log(f"Merge final com {len(df)} linhas")

    # =========================
    # GARANTIR COLUNAS
    # =========================
    for col in [
        "Código",
        "GTIN",
        "Produto",
        "Preço",
        "Preço Custo",
        "Descrição Curta",
        "Descrição Complementar",
        "Imagem",
        "Link",
        "Marca",
        "Estoque",
        "NCM",
        "Origem",
        "Peso Líquido",
        "Peso Bruto",
        "Estoque Mínimo",
        "Estoque Máximo",
        "Unidade",
        "Tipo",
        "Situação",
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")

    # =========================
    # BLING
    # =========================
    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    log(f"Planilha estoque gerada com {len(df_estoque)} linhas")
    log(f"Planilha cadastro gerada com {len(df_cadastro)} linhas")

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
    # RESULTADO
    # =========================
    st.success("✅ Arquivos prontos")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "📥 ESTOQUE",
            csv_estoque,
            "estoque.csv",
            mime="text/csv"
        )

    with col2:
        st.download_button(
            "📥 CADASTRO",
            csv_cadastro,
            "cadastro.csv",
            mime="text/csv"
        )

    with col3:
        st.download_button(
            "📦 BAIXAR TUDO",
            zip_buffer.getvalue(),
            "bling.zip",
            mime="application/zip"
        )

    with st.expander("Visualizar base final"):
        st.dataframe(df.head(50))

    with st.expander("Visualizar estoque"):
        st.dataframe(df_estoque.head(50))

    with st.expander("Visualizar cadastro"):
        st.dataframe(df_cadastro.head(50))

# =========================
# LOG + DOWNLOAD
# =========================
if logs:
    st.warning("📄 LOG DEBUG")

    log_texto = "\n".join(logs)

    st.text_area("Log completo", log_texto, height=300)

    st.download_button(
        label="📥 Baixar LOG (TXT)",
        data=log_texto,
        file_name="debug_log.txt",
        mime="text/plain"
    )
