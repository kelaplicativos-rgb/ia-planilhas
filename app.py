import io
import zipfile

import pandas as pd
import streamlit as st
import urllib3

from core.logger import logs, log
from core.reader import ler_planilha
from core.scraper import coletar_links_site, rodar_fila_async
from core.normalizer import normalizar_planilha_entrada
from core.bling.estoque import preencher_modelo_estoque
from core.bling.cadastro import preencher_modelo_cadastro
from core.merger import merge_dados

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE")

MAX_WORKERS = 2


class UploadedBuffer(io.BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def upload_para_bytes(uploaded_file):
    if uploaded_file is None:
        return None, None
    return uploaded_file.getvalue(), uploaded_file.name


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

    df = df[colunas_necessarias].fillna("")

    df["Produto"] = df["Produto"].astype(str).str.strip()
    df["Descrição Curta"] = df["Descrição Curta"].astype(str).str.strip()

    df["Descrição Curta"] = df.apply(
        lambda r: r["Descrição Curta"] if r["Descrição Curta"] else r["Produto"],
        axis=1,
    )

    df = df[df["Produto"] != ""].copy()

    return df.reset_index(drop=True)


def montar_zip_profissional(csv_estoque: str, csv_cadastro: str, log_texto: str):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)
        z.writestr("debug_log.txt", log_texto or "")

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


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

col1, col2 = st.columns(2)

with col1:
    modelo_estoque_file = st.file_uploader(
        "📦 Modelo ESTOQUE (Bling)",
        type=["xlsx", "xls", "csv"],
    )

with col2:
    modelo_cadastro_file = st.file_uploader(
        "📋 Modelo CADASTRO (Bling)",
        type=["xlsx", "xls", "csv"],
    )

col3, col4 = st.columns(2)

with col3:
    estoque_padrao = st.number_input("📦 Estoque padrão", value=10, min_value=0)

with col4:
    depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")

depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]


def executar_fluxo():
    logs.clear()
    log("🔥 EXECUTANDO FLUXO 🔥")

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling.")
        return None

    if not depositos:
        st.error("❌ Informe pelo menos um depósito.")
        return None

    status = st.empty()
    progress = st.progress(0)

    status.info("Lendo modelos do Bling...")

    est_bytes, est_name = upload_para_bytes(modelo_estoque_file)
    cad_bytes, cad_name = upload_para_bytes(modelo_cadastro_file)

    modelo_est = ler_planilha(UploadedBuffer(est_bytes, est_name))
    modelo_cad = ler_planilha(UploadedBuffer(cad_bytes, cad_name))

    if modelo_est is None or modelo_cad is None:
        st.error("❌ Não foi possível ler os modelos do Bling.")
        return None

    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("❌ Envie a planilha de dados.")
            return None

        status.info("Lendo planilha de dados...")

        dados_bytes, dados_name = upload_para_bytes(arquivo_dados)
        entrada = ler_planilha(UploadedBuffer(dados_bytes, dados_name))

        if entrada is None or entrada.empty:
            st.error("❌ Não foi possível ler a planilha de dados.")
            return None

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base=url_base,
            estoque_padrao=estoque_padrao,
        )

    progress.progress(0.35)

    df_site = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Site"]:
        status.info("Coletando links do site...")

        links = coletar_links_site(url_base)

        if modo_coleta == "Só Site" and not links:
            st.error("❌ Nenhum link de produto foi encontrado no site.")
            return None

        if len(links) > 180:
            links = links[:180]
            log("Links limitados a 180 para estabilidade.")

        status.info("Processando produtos do site...")

        produtos = rodar_fila_async(
            links=links,
            filtro="",
            estoque_padrao=estoque_padrao,
            concorrencia=MAX_WORKERS,
        )

        df_site = pd.DataFrame(produtos)

    progress.progress(0.70)

    status.info("Fazendo merge final...")

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
    df = garantir_colunas_finais(df)

    if df is None or df.empty:
        st.error("❌ Nenhum dado final gerado.")
        return None

    if len(df) > 300:
        df = df.head(300).copy()
        log("Base final limitada a 300 produtos para estabilidade.")

    progress.progress(0.82)

    status.info("Gerando planilhas do Bling...")

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    progress.progress(0.92)

    status.info("Preparando ZIP...")

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")
    log_texto = "\n".join(logs)

    zip_bytes = montar_zip_profissional(
        csv_estoque=csv_estoque,
        csv_cadastro=csv_cadastro,
        log_texto=log_texto,
    )

    progress.progress(1.0)
    status.success("Processamento concluído.")

    return {
        "zip_bytes": zip_bytes,
    }


if st.button("🚀 EXECUTAR PROCESSAMENTO"):
    resultado = executar_fluxo()

    if resultado:
        st.success("✅ Pacote pronto")

        st.download_button(
            "📦 BAIXAR PACOTE PROFISSIONAL",
            resultado["zip_bytes"],
            "bling.zip",
            mime="application/zip",
            use_container_width=True,
        )
