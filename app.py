import io
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
st.caption("Modo produção + modo diagnóstico por blocos")

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


def formatar_tempo(segundos: float) -> str:
    segundos = int(max(0, segundos))
    minutos = segundos // 60
    resto = segundos % 60
    if minutos > 0:
        return f"{minutos}m {resto}s"
    return f"{resto}s"


def atualizar_progresso(progress_bar, progresso_box, valor: float, etapa: str, inicio: float, atual=None, total=None):
    valor = max(0.0, min(1.0, valor))
    progress_bar.progress(valor)

    percentual = int(valor * 100)
    tempo_decorrido = formatar_tempo(time.time() - inicio)

    if atual is not None and total is not None and total > 0:
        progresso_box.caption(
            f"⏳ {etapa}\n"
            f"**{percentual}%** concluído — {atual}/{total} itens — tempo: **{tempo_decorrido}**"
        )
    else:
        progresso_box.caption(
            f"⏳ {etapa}\n"
            f"**{percentual}%** concluído — tempo: **{tempo_decorrido}**"
        )


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


def registrar_etapa(relatorio, etapa, ok, tempo, detalhes="", erro=""):
    relatorio.append({
        "Etapa": etapa,
        "Status": "OK" if ok else "ERRO",
        "Tempo": formatar_tempo(tempo),
        "Detalhes": detalhes,
        "Erro": erro,
    })


def relatorio_para_txt(relatorio):
    linhas = []
    linhas.append("RELATÓRIO DE DIAGNÓSTICO")
    linhas.append("=" * 50)

    for item in relatorio:
        linhas.append(f"Etapa: {item['Etapa']}")
        linhas.append(f"Status: {item['Status']}")
        if item.get("Detalhes"):
            linhas.append(f"Detalhes: {item['Detalhes']}")
        if item.get("Erro"):
            linhas.append(f"Erro: {item['Erro']}")
        linhas.append(f"Tempo: {item['Tempo']}")
        linhas.append("-" * 50)

    return "\n".join(linhas)


if "resultado_execucao" not in st.session_state:
    st.session_state.resultado_execucao = None

if "resultado_diagnostico" not in st.session_state:
    st.session_state.resultado_diagnostico = None


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

    diagnostico_amostra_links = st.selectbox(
        "Amostra de links no diagnóstico",
        [5, 10, 15, 20, 30, 50],
        index=2,
    )

depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

with st.expander("📁 Arquivos", expanded=True):
    arquivo_dados = st.file_uploader("Planilha de dados", type=["xlsx", "xls", "csv"])
    modelo_estoque_file = st.file_uploader("Modelo ESTOQUE (Bling)", type=["xlsx", "xls", "csv"])
    modelo_cadastro_file = st.file_uploader("Modelo CADASTRO (Bling)", type=["xlsx", "xls", "csv"])


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

    inicio = time.time()
    status = st.empty()
    progress = st.progress(0)
    progresso_info = st.empty()

    status.info("Lendo modelos do Bling...")
    atualizar_progresso(progress, progresso_info, 0.05, "Lendo modelos do Bling", inicio)

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
        atualizar_progresso(progress, progresso_info, 0.15, "Lendo planilha de dados", inicio)

        dados_bytes, dados_name = upload_para_bytes(arquivo_dados)
        entrada = ler_planilha(UploadedBuffer(dados_bytes, dados_name))

        if entrada is None or entrada.empty:
            st.error("❌ Não foi possível ler a planilha de dados.")
            return None

        status.info("Normalizando planilha...")
        atualizar_progresso(progress, progresso_info, 0.25, "Normalizando planilha", inicio)

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base=url_base,
            estoque_padrao=estoque_padrao,
        )

    atualizar_progresso(progress, progresso_info, 0.35, "Etapa de planilha concluída", inicio)

    df_site = pd.DataFrame()
    deve_rodar_site = (modo_coleta == "Só Site") or (modo_coleta == "Planilha + Site" and modo_execucao == "Completo")

    if deve_rodar_site:
        status.info("Coletando links do site...")
        atualizar_progresso(progress, progresso_info, 0.40, "Coletando links do site", inicio)

        links = coletar_links_site(url_base)

        if modo_execucao == "Rápido" and len(links) > 60:
            links = links[:60]

        if modo_execucao == "Completo" and len(links) > 120:
            links = links[:120]

        produtos = []

        if links:
            status.info("Extraindo produtos do site...")
            total = len(links)

            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(extrair_site, link, "", estoque_padrao) for link in links]

                for i, future in enumerate(as_completed(futures), start=1):
                    try:
                        resultado = future.result()
                        if resultado:
                            produtos.append(resultado)
                    except Exception as e:
                        log(f"ERRO scraper: {e}")

                    progresso_atual = 0.40 + (0.30 * (i / total))
                    atualizar_progresso(
                        progress,
                        progresso_info,
                        progresso_atual,
                        "Extraindo produtos do site",
                        inicio,
                        i,
                        total,
                    )

        df_site = pd.DataFrame(produtos)

    else:
        atualizar_progresso(progress, progresso_info, 0.70, "Etapa de site ignorada", inicio)

    status.info("Fazendo merge final...")
    atualizar_progresso(progress, progresso_info, 0.80, "Fazendo merge final", inicio)

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
    df = garantir_colunas_finais(df)

    if df is None or df.empty:
        st.error("❌ Nenhum dado final gerado.")
        return None

    if len(df) > 250:
        df = df.head(250).copy()
        log("Base final limitada a 250 produtos para estabilidade.")

    status.info("Gerando planilhas do Bling...")
    atualizar_progresso(progress, progresso_info, 0.90, "Gerando planilhas do Bling", inicio)

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    status.info("Preparando ZIP...")
    atualizar_progresso(progress, progresso_info, 0.96, "Preparando ZIP", inicio)

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")
    log_texto = "\n".join(logs)

    zip_bytes = montar_zip_profissional(
        csv_estoque=csv_estoque,
        csv_cadastro=csv_cadastro,
        log_texto=log_texto,
    )

    status.success("Processamento concluído.")
    atualizar_progresso(progress, progresso_info, 1.0, "Processamento concluído", inicio)

    return {
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "zip_bytes": zip_bytes,
        "metricas": calcular_metricas(df, df_estoque, df_cadastro),
    }


def executar_diagnostico():
    logs.clear()
    log("🧪 EXECUTANDO DIAGNÓSTICO POR BLOCOS 🧪")

    relatorio = []
    inicio_global = time.time()

    status = st.empty()
    progress = st.progress(0)
    progresso_info = st.empty()

    modelo_est = None
    modelo_cad = None
    entrada = None
    df_planilha = pd.DataFrame()
    links = []
    produtos = []
    df_site = pd.DataFrame()
    df_final = pd.DataFrame()
    df_estoque = pd.DataFrame()
    df_cadastro = pd.DataFrame()

    etapas_total = 10
    etapa_atual = 0

    def avanca(etapa_nome):
        nonlocal etapa_atual
        etapa_atual += 1
        atualizar_progresso(
            progress,
            progresso_info,
            etapa_atual / etapas_total,
            etapa_nome,
            inicio_global,
        )

    # 1. modelo estoque
    t0 = time.time()
    try:
        status.info("Testando leitura do modelo estoque...")
        if not modelo_estoque_file:
            raise ValueError("Modelo ESTOQUE não enviado")

        est_bytes, est_name = upload_para_bytes(modelo_estoque_file)
        modelo_est = ler_planilha(UploadedBuffer(est_bytes, est_name))

        if modelo_est is None or modelo_est.empty:
            raise ValueError("Modelo ESTOQUE vazio ou inválido")

        registrar_etapa(
            relatorio,
            "Leitura modelo estoque",
            True,
            time.time() - t0,
            f"{len(modelo_est)} linhas | {len(modelo_est.columns)} colunas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Leitura modelo estoque", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura do modelo estoque")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Leitura modelo estoque OK")

    # 2. modelo cadastro
    t0 = time.time()
    try:
        status.info("Testando leitura do modelo cadastro...")
        if not modelo_cadastro_file:
            raise ValueError("Modelo CADASTRO não enviado")

        cad_bytes, cad_name = upload_para_bytes(modelo_cadastro_file)
        modelo_cad = ler_planilha(UploadedBuffer(cad_bytes, cad_name))

        if modelo_cad is None or modelo_cad.empty:
            raise ValueError("Modelo CADASTRO vazio ou inválido")

        registrar_etapa(
            relatorio,
            "Leitura modelo cadastro",
            True,
            time.time() - t0,
            f"{len(modelo_cad)} linhas | {len(modelo_cad.columns)} colunas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Leitura modelo cadastro", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura do modelo cadastro")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Leitura modelo cadastro OK")

    # 3. leitura planilha dados
    t0 = time.time()
    try:
        status.info("Testando leitura da planilha de dados...")

        if modo_coleta in ["Planilha + Site", "Só Planilha"]:
            if not arquivo_dados:
                raise ValueError("Planilha de dados não enviada")

            dados_bytes, dados_name = upload_para_bytes(arquivo_dados)
            entrada = ler_planilha(UploadedBuffer(dados_bytes, dados_name))

            if entrada is None or entrada.empty:
                raise ValueError("Planilha de dados vazia ou inválida")

            detalhe = f"{len(entrada)} linhas | {len(entrada.columns)} colunas"
        else:
            detalhe = "Etapa ignorada neste modo"

        registrar_etapa(relatorio, "Leitura planilha de dados", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Leitura planilha de dados", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura da planilha")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Leitura planilha OK")

    # 4. normalização
    t0 = time.time()
    try:
        status.info("Testando normalização da planilha...")

        if entrada is not None and not entrada.empty:
            df_planilha = normalizar_planilha_entrada(
                entrada,
                url_base=url_base,
                estoque_padrao=estoque_padrao,
            )
            detalhe = f"{len(df_planilha)} linhas após normalização"
        else:
            detalhe = "Etapa ignorada neste modo"

        registrar_etapa(relatorio, "Normalização da planilha", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Normalização da planilha", False, time.time() - t0, erro=str(e))
        avanca("Erro na normalização")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Normalização OK")

    # 5. coleta links
    t0 = time.time()
    try:
        status.info("Testando coleta de links...")

        if modo_coleta in ["Planilha + Site", "Só Site"]:
            links = coletar_links_site(url_base)
            detalhe = f"{len(links)} links coletados"
        else:
            detalhe = "Etapa ignorada neste modo"

        registrar_etapa(relatorio, "Coleta de links", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Coleta de links", False, time.time() - t0, erro=str(e))
        avanca("Erro na coleta de links")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Coleta de links OK")

    # 6. extração produtos site
    t0 = time.time()
    try:
        status.info("Testando extração de produtos...")

        if modo_coleta in ["Planilha + Site", "Só Site"] and links:
            amostra = links[:diagnostico_amostra_links]
            for link in amostra:
                try:
                    r = extrair_site(link, "", estoque_padrao)
                    if r:
                        produtos.append(r)
                except Exception as ex:
                    log(f"Falha extração diagnóstico: {ex}")

            df_site = pd.DataFrame(produtos)
            detalhe = f"{len(produtos)} produtos extraídos em {len(amostra)} links testados"
        else:
            detalhe = "Etapa ignorada neste modo"

        registrar_etapa(relatorio, "Extração de produtos do site", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Extração de produtos do site", False, time.time() - t0, erro=str(e))
        avanca("Erro na extração do site")
        return {
            "relatorio": pd.DataFrame(relatorio),
            "txt": relatorio_para_txt(relatorio),
        }
    avanca("Extração do site OK")

    # 7. merge
    t0 = time.time()
    try:
        status.info("Testando merge final...")

        df_final = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
        df_final = garantir_colunas_finais(df_final)

        if df_final is None or df_final.empty:
            raise ValueError("Merge não gerou dados válidos")

        registrar_etapa(
            relatorio,
            "Merge final",
            True,
            time.time() - t0,
            f"{len(df_final)} linhas após merge",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Merge final", False, time.time() - t0, erro=str(e))
        avanca("Erro no merge")
        return {
            "relatorio": pd.DataFrame(relatorio)
