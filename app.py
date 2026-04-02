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

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE SaaS", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE SaaS")


# =========================
# CONFIG
# =========================
MAX_WORKERS_RAPIDO = 2
MAX_WORKERS_COMPLETO = 3


# =========================
# HELPERS DE CACHE
# =========================
class UploadedBuffer(io.BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


@st.cache_data(show_spinner=False)
def ler_planilha_cache(file_bytes: bytes, file_name: str):
    fake_file = UploadedBuffer(file_bytes, file_name)
    return ler_planilha(fake_file)


@st.cache_data(show_spinner=False)
def normalizar_planilha_cache(df: pd.DataFrame, url_base: str, estoque_padrao: int):
    return normalizar_planilha_entrada(df, url_base=url_base, estoque_padrao=estoque_padrao)


@st.cache_data(show_spinner=False)
def coletar_links_site_cache(url_base: str):
    return coletar_links_site(url_base)


# =========================
# HELPERS GERAIS
# =========================
def upload_para_bytes(uploaded_file):
    if uploaded_file is None:
        return None, None
    return uploaded_file.getvalue(), uploaded_file.name


def maybe_log(msg: str, debug_mode: bool):
    if debug_mode:
        log(msg)


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

    for col in ["Código", "Produto", "Descrição Curta", "Marca", "Link", "Imagem"]:
        df[col] = df[col].astype(str).str.strip()

    df["Descrição Curta"] = df.apply(
        lambda r: r["Descrição Curta"] if r["Descrição Curta"] else r["Produto"],
        axis=1,
    )

    df = df[df["Produto"] != ""].copy()

    return df.reset_index(drop=True)


def calcular_metricas(df_base, df_estoque, df_cadastro):
    metricas = {
        "produtos_finais": 0,
        "estoque_linhas": 0,
        "cadastro_linhas": 0,
        "sem_gtin": 0,
        "sem_marca": 0,
        "sem_imagem": 0,
        "sem_link": 0,
        "sem_ncm": 0,
        "sem_preco_custo": 0,
    }

    if df_base is not None and not df_base.empty:
        metricas["produtos_finais"] = len(df_base)
        metricas["sem_gtin"] = int((df_base["GTIN"].astype(str).str.strip() == "").sum()) if "GTIN" in df_base.columns else 0
        metricas["sem_marca"] = int((df_base["Marca"].astype(str).str.strip() == "").sum()) if "Marca" in df_base.columns else 0
        metricas["sem_imagem"] = int((df_base["Imagem"].astype(str).str.strip() == "").sum()) if "Imagem" in df_base.columns else 0
        metricas["sem_link"] = int((df_base["Link"].astype(str).str.strip() == "").sum()) if "Link" in df_base.columns else 0
        metricas["sem_ncm"] = int((df_base["NCM"].astype(str).str.strip() == "").sum()) if "NCM" in df_base.columns else 0
        metricas["sem_preco_custo"] = int((df_base["Preço Custo"].astype(str).str.strip() == "").sum()) if "Preço Custo" in df_base.columns else 0

    if df_estoque is not None and not df_estoque.empty:
        metricas["estoque_linhas"] = len(df_estoque)

    if df_cadastro is not None and not df_cadastro.empty:
        metricas["cadastro_linhas"] = len(df_cadastro)

    return metricas


def filtrar_preview(df: pd.DataFrame, termo: str):
    if df is None or df.empty:
        return df

    termo = (termo or "").strip().lower()
    if not termo:
        return df

    mascara = pd.Series([False] * len(df), index=df.index)

    for col in df.columns:
        try:
            mascara = mascara | df[col].astype(str).str.lower().str.contains(termo, na=False)
        except Exception:
            pass

    return df[mascara].copy()


def mostrar_preview(df: pd.DataFrame, titulo: str, termo_filtro: str, limite: int):
    with st.expander(titulo):
        if df is None or df.empty:
            st.info("Sem dados para mostrar.")
            return

        filtrado = filtrar_preview(df, termo_filtro)
        st.write(f"Registros exibidos: {min(len(filtrado), limite)} / {len(filtrado)}")
        st.dataframe(filtrado.head(limite), use_container_width=True)


def exportar_excel_memoria(df_estoque: pd.DataFrame, df_cadastro: pd.DataFrame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_estoque.to_excel(writer, index=False, sheet_name="Estoque")
        df_cadastro.to_excel(writer, index=False, sheet_name="Cadastro")
    output.seek(0)
    return output.getvalue()


# =========================
# SIDEBAR SaaS
# =========================
with st.sidebar:
    st.header("⚙️ Controles SaaS")

    modo_execucao = st.radio(
        "⚡ Modo",
        ["Rápido", "Completo"],
        horizontal=False,
    )

    debug_mode = st.checkbox("🛠 Debug completo", value=True)
    mostrar_previews = st.checkbox("👀 Mostrar prévias", value=True)
    usar_cache = st.checkbox("💾 Usar cache", value=True)
    limitar_scraper = st.checkbox("🚀 Scraper enxuto", value=True)
    usar_site_para_complementar = st.checkbox(
        "🌐 Complementar com site",
        value=True,
    )

    limite_preview = st.slider("📄 Linhas na prévia", 10, 200, 30, 10)
    termo_preview = st.text_input("🔎 Filtro da prévia")

    if st.button("🧹 Limpar cache"):
        st.cache_data.clear()
        st.success("Cache limpo.")

    if st.button("🗑 Limpar log"):
        logs.clear()
        st.success("Log limpo.")


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


# =========================
# FLUXO PRINCIPAL
# =========================
def executar_fluxo():
    logs.clear()
    log("🔥 EXECUTANDO FLUXO SaaS 🔥")

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling: estoque e cadastro.")
        return None

    if not depositos:
        st.error("❌ Informe pelo menos um depósito.")
        return None

    workers = MAX_WORKERS_RAPIDO if modo_execucao == "Rápido" else MAX_WORKERS_COMPLETO
    maybe_log(f"Modo: {modo_execucao} | workers={workers}", debug_mode)

    progress = st.progress(0)
    status = st.empty()

    # =========================
    # MODELOS
    # =========================
    status.info("Lendo modelos do Bling...")

    est_bytes, est_name = upload_para_bytes(modelo_estoque_file)
    cad_bytes, cad_name = upload_para_bytes(modelo_cadastro_file)

    if usar_cache:
        modelo_est = ler_planilha_cache(est_bytes, est_name)
        modelo_cad = ler_planilha_cache(cad_bytes, cad_name)
    else:
        modelo_est = ler_planilha(UploadedBuffer(est_bytes, est_name))
        modelo_cad = ler_planilha(UploadedBuffer(cad_bytes, cad_name))

    if modelo_est is None or modelo_cad is None:
        st.error("❌ Não foi possível ler um dos modelos do Bling.")
        return None

    # =========================
    # PLANILHA
    # =========================
    df_planilha = pd.DataFrame()

    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        status.info("Lendo planilha de dados...")

        if not arquivo_dados:
            st.error("❌ Envie a planilha de dados.")
            return None

        dados_bytes, dados_name = upload_para_bytes(arquivo_dados)

        if usar_cache:
            entrada = ler_planilha_cache(dados_bytes, dados_name)
        else:
            entrada = ler_planilha(UploadedBuffer(dados_bytes, dados_name))

        if entrada is None or entrada.empty:
            st.error("❌ Não foi possível ler a planilha de dados.")
            return None

        maybe_log(f"Planilha de entrada lida com {len(entrada)} linhas", debug_mode)

        status.info("Normalizando planilha...")

        if usar_cache:
            df_planilha = normalizar_planilha_cache(entrada, url_base, estoque_padrao)
        else:
            df_planilha = normalizar_planilha_entrada(
                entrada,
                url_base=url_base,
                estoque_padrao=estoque_padrao,
            )

        if df_planilha is None:
            df_planilha = pd.DataFrame()

        maybe_log(f"Planilha normalizada com {len(df_planilha)} linhas", debug_mode)

    progress.progress(0.35)

    # =========================
    # SITE
    # =========================
    df_site = pd.DataFrame()

    deve_rodar_site = (
        modo_coleta == "Só Site"
        or (modo_coleta == "Planilha + Site" and usar_site_para_complementar)
    )

    if deve_rodar_site:
        status.info("Coletando links do site...")

        if usar_cache:
            links = coletar_links_site_cache(url_base)
        else:
            links = coletar_links_site(url_base)

        maybe_log(f"Links coletados: {len(links)}", debug_mode)

        if not links and modo_coleta == "Só Site":
            st.error("❌ Nenhum link de produto foi encontrado no site.")
            return None

        if limitar_scraper and modo_execucao == "Rápido" and len(links) > 80:
            links = links[:80]
            maybe_log("Modo rápido: links limitados para acelerar", debug_mode)

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

                    progresso_site = 0.35 + (0.35 * (i / total))
                    progress.progress(min(progresso_site, 0.70))

        df_site = pd.DataFrame(produtos)
        maybe_log(f"Produtos extraídos do site: {len(df_site)}", debug_mode)

    else:
        progress.progress(0.70)

    # =========================
    # MERGE
    # =========================
    status.info("Fazendo merge final...")

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df is None or (hasattr(df, "empty") and df.empty):
        st.error("❌ Nenhum dado encontrado após merge.")
        log("Nenhum dado encontrado após merge")
        return None

    df = garantir_colunas_finais(df)
    maybe_log(f"Merge final com {len(df)} linhas", debug_mode)

    if df.empty:
        st.error("❌ Nenhum produto válido restou após a limpeza final.")
        log("Nenhum produto válido restou após limpeza final")
        return None

    progress.progress(0.82)

    # =========================
    # BLING
    # =========================
    status.info("Gerando planilhas do Bling...")

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    maybe_log(f"Planilha estoque gerada com {len(df_estoque)} linhas", debug_mode)
    maybe_log(f"Planilha cadastro gerada com {len(df_cadastro)} linhas", debug_mode)

    progress.progress(0.92)

    # =========================
    # EXPORT
    # =========================
    status.info("Preparando downloads...")

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")
    excel_bytes = exportar_excel_memoria(df_estoque, df_cadastro)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)
        z.writestr("bling.xlsx", excel_bytes)
    zip_buffer.seek(0)

    progress.progress(1.0)
    status.success("Processamento concluído.")

    metricas = calcular_metricas(df, df_estoque, df_cadastro)

    return {
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "csv_estoque": csv_estoque,
        "csv_cadastro": csv_cadastro,
        "excel_bytes": excel_bytes,
        "zip_bytes": zip_buffer.getvalue(),
        "metricas": metricas,
    }


# =========================
# BOTÃO
# =========================
if st.button("🚀 EXECUTAR PROCESSAMENTO"):
    resultado = executar_fluxo()

    if resultado:
        st.success("✅ Arquivos prontos para importação no Bling")

        m = resultado["metricas"]

        a, b, c, d = st.columns(4)
        a.metric("Produtos finais", m["produtos_finais"])
        b.metric("Linhas estoque", m["estoque_linhas"])
        c.metric("Linhas cadastro", m["cadastro_linhas"])
        d.metric("Sem GTIN", m["sem_gtin"])

        e, f, g, h = st.columns(4)
        e.metric("Sem marca", m["sem_marca"])
        f.metric("Sem imagem", m["sem_imagem"])
        g.metric("Sem link", m["sem_link"])
        h.metric("Sem NCM", m["sem_ncm"])

        st.caption(
            f"Sem preço de custo: {m['sem_preco_custo']} | "
            f"Depósitos usados: {', '.join(depositos)} | "
            f"Modo: {modo_execucao}"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.download_button(
                "📥 ESTOQUE CSV",
                resultado["csv_estoque"],
                "estoque.csv",
                mime="text/csv",
            )

        with col2:
            st.download_button(
                "📥 CADASTRO CSV",
                resultado["csv_cadastro"],
                "cadastro.csv",
                mime="text/csv",
            )

        with col3:
            st.download_button(
                "📗 BLING XLSX",
                resultado["excel_bytes"],
                "bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        with col4:
            st.download_button(
                "📦 PACOTE COMPLETO",
                resultado["zip_bytes"],
                "bling.zip",
                mime="application/zip",
            )

        if mostrar_previews:
            mostrar_preview(resultado["df"], "📄 Base final", termo_preview, limite_preview)
            mostrar_preview(resultado["df_estoque"], "📦 Estoque", termo_preview, limite_preview)
            mostrar_preview(resultado["df_cadastro"], "📋 Cadastro", termo_preview, limite_preview)


# =========================
# LOG + DOWNLOAD
# =========================
if logs:
    st.warning("📄 LOG DEBUG")

    log_texto = "\n".join(logs)

    if debug_mode:
        st.text_area("Log completo", log_texto, height=320)

    st.download_button(
        label="📥 Baixar LOG (TXT)",
        data=log_texto,
        file_name="debug_log.txt",
        mime="text/plain",
    )
