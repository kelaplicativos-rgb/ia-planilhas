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

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE TURBO", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE TURBO")

MAX_WORKERS_RAPIDO = 1
MAX_WORKERS_COMPLETO = 2


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
        "Código", "GTIN", "Produto", "Preço", "Preço Custo",
        "Descrição Curta", "Descrição Complementar", "Imagem", "Link",
        "Marca", "Estoque", "NCM", "Origem", "Peso Líquido", "Peso Bruto",
        "Estoque Mínimo", "Estoque Máximo", "Unidade", "Tipo", "Situação",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=colunas_necessarias)

    df = df.copy()

    for col in colunas_necessarias:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_necessarias].fillna("")
    df["Descrição Curta"] = df.apply(
        lambda r: r["Descrição Curta"] if str(r["Descrição Curta"]).strip() else str(r["Produto"]).strip(),
        axis=1,
    )
    df = df[df["Produto"].astype(str).str.strip() != ""].copy()

    return df.reset_index(drop=True)


def montar_zip_profissional(csv_estoque: str, csv_cadastro: str, log_texto: str):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)
        z.writestr("debug_log.txt", log_texto or "")
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


with st.sidebar:
    st.header("⚙️ Controles Turbo")
    modo_execucao = st.radio("⚡ Modo", ["Rápido", "Completo"])
    debug_mode = st.checkbox("🛠 Debug completo", value=True)
    mostrar_previews = st.checkbox("👀 Mostrar prévias", value=True)
    limite_preview = st.slider("📄 Linhas na prévia", 10, 100, 20, 10)


modo_coleta = st.radio(
    "📥 Fonte dos dados",
    ["Planilha + Site", "Só Planilha", "Só Site"],
    horizontal=True,
)

url_base = st.text_input("🌐 Site:", "https://megacentereletronicos.com.br/")

arquivo_dados = st.file_uploader("📄 Planilha de dados", type=["xlsx", "xls", "csv"])
modelo_estoque_file = st.file_uploader("📦 Modelo ESTOQUE (Bling)", type=["xlsx", "xls", "csv"])
modelo_cadastro_file = st.file_uploader("📋 Modelo CADASTRO (Bling)", type=["xlsx", "xls", "csv"])

col1, col2 = st.columns(2)
with col1:
    estoque_padrao = st.number_input("📦 Estoque padrão", value=10, min_value=0)
with col2:
    depositos_input = st.text_input("🏬 Depósitos (vírgula)", "1")

depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]


def executar_fluxo():
    logs.clear()
    log("🔥 EXECUTANDO FLUXO SaaS 🔥")

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling.")
        return None

    if not depositos:
        st.error("❌ Informe pelo menos um depósito.")
        return None

    workers = MAX_WORKERS_RAPIDO if modo_execucao == "Rápido" else MAX_WORKERS_COMPLETO

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
    deve_rodar_site = (modo_coleta == "Só Site") or (modo_coleta == "Planilha + Site" and modo_execucao == "Completo")

    if deve_rodar_site:
        status.info("Coletando links do site...")
        links = coletar_links_site(url_base)

        if modo_execucao == "Rápido" and len(links) > 60:
            links = links[:60]

        if modo_execucao == "Completo" and len(links) > 120:
            links = links[:120]

        produtos = []

        if links:
            status.info("Extraindo produtos do site...")
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(extrair_site, link, "", estoque_padrao) for link in links]
                total = len(links)

                for i, future in enumerate(as_completed(futures), start=1):
                    try:
                        resultado = future.result()
                        if resultado:
                            produtos.append(resultado)
                    except Exception as e:
                        log(f"ERRO scraper: {e}")

                    progress.progress(0.35 + (0.35 * (i / total)))

        df_site = pd.DataFrame(produtos)

    else:
        progress.progress(0.70)

    status.info("Fazendo merge final...")
    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
    df = garantir_colunas_finais(df)

    if df is None or df.empty:
        st.error("❌ Nenhum dado final gerado.")
        return None

    if len(df) > 250:
        df = df.head(250).copy()
        log("Base final limitada a 250 produtos para estabilidade.")

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
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
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

        if mostrar_previews:
            with st.expander("📄 Base final"):
                st.dataframe(resultado["df"].head(limite_preview), use_container_width=True)

            with st.expander("📦 Estoque"):
                st.dataframe(resultado["df_estoque"].head(limite_preview), use_container_width=True)

            with st.expander("📋 Cadastro"):
                st.dataframe(resultado["df_cadastro"].head(limite_preview), use_container_width=True)


if logs:
    st.warning("📄 LOG DEBUG")
    log_texto = "\n".join(logs)

    if debug_mode:
        st.text_area("Log completo", log_texto, height=300)

    st.download_button(
        label="📥 Baixar LOG (TXT)",
        data=log_texto,
        file_name="debug_log.txt",
        mime="text/plain",
    )
