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

estoque_padrao = st.number_input("📦 Estoque padrão", value=10, min_value=0)

depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")
depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]


# =========================
# HELPERS
# =========================
def garantir_colunas_finais(df: pd.DataFrame) -> pd.DataFrame:
    colunas_necessarias = [
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
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=colunas_necessarias)

    df = df.copy()

    for col in colunas_necessarias:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_necessarias].copy()
    df = df.fillna("")

    df["Código"] = df["Código"].astype(str).str.strip()
    df["Produto"] = df["Produto"].astype(str).str.strip()
    df["Descrição Curta"] = df["Descrição Curta"].astype(str).str.strip()

    # descrição curta nunca vazia
    df["Descrição Curta"] = df.apply(
        lambda r: r["Descrição Curta"] if r["Descrição Curta"] else r["Produto"],
        axis=1,
    )

    # remove linhas sem produto
    df = df[df["Produto"] != ""].copy()

    return df.reset_index(drop=True)


def executar_fluxo():
    logs.clear()
    log("🔥 EXECUTANDO FLUXO 🔥")

    # =========================
    # VALIDAÇÃO INICIAL
    # =========================
    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling: estoque e cadastro.")
        return None

    if not depositos:
        st.error("❌ Informe pelo menos um depósito.")
        return None

    # =========================
    # LEITURA MODELOS
    # =========================
    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.error("❌ Não foi possível ler um dos modelos do Bling.")
        return None

    progress = st.progress(0)

    # =========================
    # PLANILHA
    # =========================
    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        log("Modo com planilha ativado")

        if not arquivo_dados:
            st.error("❌ Envie a planilha de dados.")
            return None

        entrada = ler_planilha(arquivo_dados)

        if entrada is None or entrada.empty:
            st.error("❌ Não foi possível ler a planilha de dados.")
            return None

        log(f"Planilha de entrada lida com {len(entrada)} linhas")

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base=url_base,
            estoque_padrao=estoque_padrao,
        )

        if df_planilha is None:
            df_planilha = pd.DataFrame()

        log(f"Planilha normalizada com {len(df_planilha)} linhas")

    # =========================
    # SITE
    # =========================
    df_site = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Site"]:
        log("Modo com site ativado")

        links = coletar_links_site(url_base)
        log(f"Total de links retornados pela coleta: {len(links)}")

        if not links and modo_coleta == "Só Site":
            st.error("❌ Nenhum link de produto foi encontrado no site.")
            return None

        produtos = []

        if links:
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [
                    ex.submit(extrair_site, link, "", estoque_padrao)
                    for link in links
                ]

                total = len(links)

                for i, future in enumerate(as_completed(futures), start=1):
                    try:
                        resultado = future.result()
                        if resultado:
                            produtos.append(resultado)
                    except Exception as e:
                        log(f"ERRO scraper: {e}")

                    progress.progress(i / total)

        df_site = pd.DataFrame(produtos)
        log(f"Produtos extraídos do site: {len(df_site)}")

    # =========================
    # MERGE
    # =========================
    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df is None or (hasattr(df, "empty") and df.empty):
        st.error("❌ Nenhum dado encontrado após merge.")
        log("Nenhum dado encontrado após merge")
        return None

    df = garantir_colunas_finais(df)
    log(f"Merge final com {len(df)} linhas")

    if df.empty:
        st.error("❌ Nenhum produto válido restou após a limpeza final.")
        log("Nenhum produto válido restou após limpeza final")
        return None

    # =========================
    # GERAÇÃO BLING
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

    return {
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "csv_estoque": csv_estoque,
        "csv_cadastro": csv_cadastro,
        "zip_bytes": zip_buffer.getvalue(),
    }


# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR PROCESSAMENTO"):
    resultado = executar_fluxo()

    if resultado:
        st.success("✅ Arquivos prontos para importação no Bling")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "📥 ESTOQUE",
                resultado["csv_estoque"],
                "estoque.csv",
                mime="text/csv",
            )

        with col2:
            st.download_button(
                "📥 CADASTRO",
                resultado["csv_cadastro"],
                "cadastro.csv",
                mime="text/csv",
            )

        with col3:
            st.download_button(
                "📦 BAIXAR TUDO",
                resultado["zip_bytes"],
                "bling.zip",
                mime="application/zip",
            )

        with st.expander("📄 Visualizar base final"):
            st.dataframe(resultado["df"].head(100), use_container_width=True)

        with st.expander("📦 Visualizar estoque"):
            st.dataframe(resultado["df_estoque"].head(100), use_container_width=True)

        with st.expander("📋 Visualizar cadastro"):
            st.dataframe(resultado["df_cadastro"].head(100), use_container_width=True)


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
        mime="text/plain",
    )
