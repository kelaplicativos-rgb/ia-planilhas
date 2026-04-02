import io
import math
import time
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

st.set_page_config(
    page_title="BLING AUTO INTELIGENTE TURBO",
    layout="centered",
)

st.title("🔥 BLING AUTO INTELIGENTE TURBO")
st.caption("Modo turbo absurdo — otimizado para celular")

MAX_WORKERS_RAPIDO = 1
MAX_WORKERS_COMPLETO = 2

MAX_LINKS_RAPIDO = 40
MAX_LINKS_COMPLETO = 120

BATCH_RAPIDO = 10
BATCH_COMPLETO = 20

TIMEOUT_RAPIDO = 45
TIMEOUT_COMPLETO = 120


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


def mostrar_preview(df: pd.DataFrame, titulo: str, limite: int):
    if df is None or df.empty:
        st.info(f"{titulo}: sem dados")
        return

    st.write(f"**{titulo}**")
    st.dataframe(df.head(limite), use_container_width=True, hide_index=True)


def calcular_metricas(df_base, df_estoque, df_cadastro):
    metricas = {
        "produtos_finais": 0,
        "estoque_linhas": 0,
        "cadastro_linhas": 0,
        "sem_gtin": 0,
        "sem_marca": 0,
        "sem_imagem": 0,
        "sem_link": 0,
    }

    if df_base is not None and not df_base.empty:
        metricas["produtos_finais"] = len(df_base)
        metricas["sem_gtin"] = int((df_base["GTIN"].astype(str).str.strip() == "").sum()) if "GTIN" in df_base.columns else 0
        metricas["sem_marca"] = int((df_base["Marca"].astype(str).str.strip() == "").sum()) if "Marca" in df_base.columns else 0
        metricas["sem_imagem"] = int((df_base["Imagem"].astype(str).str.strip() == "").sum()) if "Imagem" in df_base.columns else 0
        metricas["sem_link"] = int((df_base["Link"].astype(str).str.strip() == "").sum()) if "Link" in df_base.columns else 0

    if df_estoque is not None and not df_estoque.empty:
        metricas["estoque_linhas"] = len(df_estoque)

    if df_cadastro is not None and not df_cadastro.empty:
        metricas["cadastro_linhas"] = len(df_cadastro)

    return metricas


def formatar_tempo(segundos: float) -> str:
    segundos = int(max(0, segundos))
    minutos = segundos // 60
    resto = segundos % 60

    if minutos > 0:
        return f"{minutos}m {resto}s"
    return f"{resto}s"


def atualizar_progresso(progress_bar, progresso_box, valor: float, etapa: str, inicio: float, atual: int | None = None, total: int | None = None, tempo_limite: int | None = None):
    valor = max(0.0, min(1.0, valor))
    progress_bar.progress(valor)

    percentual = int(valor * 100)
    tempo_decorrido = time.time() - inicio
    texto_tempo = f"tempo: **{formatar_tempo(tempo_decorrido)}**"

    if tempo_limite:
        restante = max(0, tempo_limite - int(tempo_decorrido))
        texto_tempo += f" • restante máx.: **{formatar_tempo(restante)}**"

    if atual is not None and total is not None and total > 0:
        progresso_box.caption(
            f"⏳ {etapa}  \n"
            f"**{percentual}%** concluído — {atual}/{total} itens — {texto_tempo}"
        )
    else:
        progresso_box.caption(
            f"⏳ {etapa}  \n"
            f"**{percentual}%** concluído — {texto_tempo}"
        )


def dividir_em_lotes(lista, tamanho_lote):
    for i in range(0, len(lista), tamanho_lote):
        yield lista[i:i + tamanho_lote]


def processar_links_em_lotes(links, estoque_padrao, workers, batch_size, progress, progresso_info, inicio, tempo_limite):
    produtos = []
    total = len(links)
    processados = 0

    lotes = list(dividir_em_lotes(links, batch_size))
    total_lotes = len(lotes)

    for idx_lote, lote in enumerate(lotes, start=1):
        if time.time() - inicio > tempo_limite:
            log("⛔ Timeout atingido, encerrando scraping para preservar estabilidade.")
            break

        log(f"Processando lote {idx_lote}/{total_lotes} com {len(lote)} links")

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(extrair_site, link, "", estoque_padrao) for link in lote]

            for future in as_completed(futures):
                if time.time() - inicio > tempo_limite:
                    log("⛔ Timeout atingido durante extração de produtos.")
                    break

                try:
                    resultado = future.result()
                    if resultado:
                        produtos.append(resultado)
                except Exception as e:
                    log(f"ERRO scraper: {e}")

                processados += 1

                progresso_atual = 0.40 + (0.30 * (processados / total))
                atualizar_progresso(
                    progress,
                    progresso_info,
                    progresso_atual,
                    f"Extraindo produtos do site — lote {idx_lote}/{total_lotes}",
                    inicio,
                    processados,
                    total,
                    tempo_limite,
                )

    return produtos


# =========================
# ESTADO
# =========================
if "resultado_execucao" not in st.session_state:
    st.session_state.resultado_execucao = None


# =========================
# CONFIGURAÇÕES
# =========================
with st.expander("⚙️ Configurações", expanded=True):
    modo_execucao = st.radio(
        "Modo",
        ["Rápido", "Completo"],
        horizontal=True,
    )

    modo_coleta = st.radio(
        "Fonte dos dados",
        ["Planilha + Site", "Só Planilha", "Só Site"],
        horizontal=True,
    )

    url_base = st.text_input("Site", "https://megacentereletronicos.com.br/")
    estoque_padrao = st.number_input("Estoque padrão", value=10, min_value=0)
    depositos_input = st.text_input("Depósitos (separados por vírgula)", "1")

    debug_mode = st.toggle("Mostrar log debug", value=True)
    mostrar_previews = st.toggle("Mostrar prévias", value=True)
    limite_preview = st.selectbox("Linhas na prévia", [10, 20, 30, 50, 100], index=1)

depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

with st.expander("📁 Arquivos", expanded=True):
    arquivo_dados = st.file_uploader("Planilha de dados", type=["xlsx", "xls", "csv"])
    modelo_estoque_file = st.file_uploader("Modelo ESTOQUE (Bling)", type=["xlsx", "xls", "csv"])
    modelo_cadastro_file = st.file_uploader("Modelo CADASTRO (Bling)", type=["xlsx", "xls", "csv"])


def executar_fluxo():
    logs.clear()
    log("🔥 EXECUTANDO FLUXO TURBO ABSURDO 🔥")

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("❌ Envie os dois modelos do Bling.")
        return None

    if not depositos:
        st.error("❌ Informe pelo menos um depósito.")
        return None

    if modo_execucao == "Rápido":
        workers = MAX_WORKERS_RAPIDO
        max_links = MAX_LINKS_RAPIDO
        batch_size = BATCH_RAPIDO
        tempo_limite = TIMEOUT_RAPIDO
    else:
        workers = MAX_WORKERS_COMPLETO
        max_links = MAX_LINKS_COMPLETO
        batch_size = BATCH_COMPLETO
        tempo_limite = TIMEOUT_COMPLETO

    inicio = time.time()
    status = st.empty()
    progress = st.progress(0)
    progresso_info = st.empty()

    status.info("Lendo modelos do Bling...")
    atualizar_progresso(progress, progresso_info, 0.05, "Lendo modelos do Bling", inicio, tempo_limite=tempo_limite)

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
        atualizar_progresso(progress, progresso_info, 0.15, "Lendo planilha de dados", inicio, tempo_limite=tempo_limite)

        dados_bytes, dados_name = upload_para_bytes(arquivo_dados)
        entrada = ler_planilha(UploadedBuffer(dados_bytes, dados_name))

        if entrada is None or entrada.empty:
            st.error("❌ Não foi possível ler a planilha de dados.")
            return None

        status.info("Normalizando planilha...")
        atualizar_progresso(progress, progresso_info, 0.25, "Normalizando planilha", inicio, tempo_limite=tempo_limite)

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base=url_base,
            estoque_padrao=estoque_padrao,
        )

    atualizar_progresso(progress, progresso_info, 0.35, "Etapa de planilha concluída", inicio, tempo_limite=tempo_limite)

    df_site = pd.DataFrame()
    deve_rodar_site = (modo_coleta == "Só Site") or (modo_coleta == "Planilha + Site" and modo_execucao == "Completo")

    if deve_rodar_site:
        status.info("Coletando links do site...")
        atualizar_progresso(progress, progresso_info, 0.40, "Coletando links do site", inicio, tempo_limite=tempo_limite)

        links = coletar_links_site(url_base)

        if len(links) > max_links:
            links = links[:max_links]
            log(f"Links limitados para estabilidade: {len(links)}")

        if links:
            status.info("Extraindo produtos em lotes...")
            produtos = processar_links_em_lotes(
                links=links,
                estoque_padrao=estoque_padrao,
                workers=workers,
                batch_size=batch_size,
                progress=progress,
                progresso_info=progresso_info,
                inicio=inicio,
                tempo_limite=tempo_limite,
            )
            df_site = pd.DataFrame(produtos)

    else:
        atualizar_progresso(progress, progresso_info, 0.70, "Etapa de site ignorada", inicio, tempo_limite=tempo_limite)

    status.info("Fazendo merge final...")
    atualizar_progresso(progress, progresso_info, 0.80, "Fazendo merge final", inicio, tempo_limite=tempo_limite)

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
    df = garantir_colunas_finais(df)

    if df is None or df.empty:
        st.error("❌ Nenhum dado final gerado.")
        return None

    if len(df) > 250:
        df = df.head(250).copy()
        log("Base final limitada a 250 produtos para estabilidade.")

    status.info("Gerando planilhas do Bling...")
    atualizar_progresso(progress, progresso_info, 0.90, "Gerando planilhas do Bling", inicio, tempo_limite=tempo_limite)

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    status.info("Preparando ZIP...")
    atualizar_progresso(progress, progresso_info, 0.96, "Preparando ZIP", inicio, tempo_limite=tempo_limite)

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")
    log_texto = "\n".join(logs)

    zip_bytes = montar_zip_profissional(
        csv_estoque=csv_estoque,
        csv_cadastro=csv_cadastro,
        log_texto=log_texto,
    )

    status.success("Processamento concluído.")
    atualizar_progresso(progress, progresso_info, 1.0, "Processamento concluído", inicio, tempo_limite=tempo_limite)

    return {
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "zip_bytes": zip_bytes,
        "metricas": calcular_metricas(df, df_estoque, df_cadastro),
    }


if st.button("🚀 EXECUTAR PROCESSAMENTO", use_container_width=True):
    st.session_state.resultado_execucao = executar_fluxo()

resultado = st.session_state.resultado_execucao

if resultado:
    st.success("✅ Pacote pronto")

    m = resultado["metricas"]

    with st.expander("📊 Resumo", expanded=True):
        c1, c2 = st.columns(2)
        c1.metric("Produtos finais", m["produtos_finais"])
        c2.metric("Linhas estoque", m["estoque_linhas"])

        c3, c4 = st.columns(2)
        c3.metric("Linhas cadastro", m["cadastro_linhas"])
        c4.metric("Sem GTIN", m["sem_gtin"])

        c5, c6 = st.columns(2)
        c5.metric("Sem marca", m["sem_marca"])
        c6.metric("Sem imagem", m["sem_imagem"])

        st.metric("Sem link", m["sem_link"])

    st.download_button(
        "📦 BAIXAR PACOTE PROFISSIONAL",
        resultado["zip_bytes"],
        "bling.zip",
        mime="application/zip",
        use_container_width=True,
    )

    if mostrar_previews:
        tab1, tab2, tab3 = st.tabs(["Base final", "Estoque", "Cadastro"])

        with tab1:
            mostrar_preview(resultado["df"], "Base final", limite_preview)

        with tab2:
            mostrar_preview(resultado["df_estoque"], "Estoque", limite_preview)

        with tab3:
            mostrar_preview(resultado["df_cadastro"], "Cadastro", limite_preview)

if logs and debug_mode:
    with st.expander("📄 Log debug", expanded=False):
        log_texto = "\n".join(logs)
        st.text_area("Log completo", log_texto, height=260)

        st.download_button(
            label="📥 Baixar LOG (TXT)",
            data=log_texto,
            file_name="debug_log.txt",
            mime="text/plain",
            use_container_width=True,
    )
