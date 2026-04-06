from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.site_crawler import executar_crawler


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# 🔥 LEITOR UNIVERSAL DE PLANILHA (CORREÇÃO CRÍTICA)
# ==========================================================
def _ler_planilha_segura(arquivo):
    try:
        nome = arquivo.name.lower()

        log_debug(f"Lendo arquivo: {nome}")

        if nome.endswith(".csv"):
            try:
                df = pd.read_csv(arquivo, encoding="utf-8")
            except Exception:
                df = pd.read_csv(arquivo, encoding="latin1")

        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)

        else:
            st.error("Formato não suportado")
            return None

        df = df.dropna(how="all")  # remove linhas vazias

        log_debug(f"Planilha carregada: {df.shape}")

        return df

    except Exception as e:
        log_debug(f"Erro leitura planilha: {e}", "ERROR")
        st.error("Erro ao ler arquivo")
        return None


# ==========================================================
# HELPERS
# ==========================================================
def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None
    estoque_padrao_site = 10

    # =========================
    # INPUT
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            log_debug("Iniciando leitura da planilha de origem")
            df_origem = _ler_planilha_segura(arquivo)

            if df_origem is None or df_origem.empty:
                log_debug("Erro ao carregar planilha de origem", "ERROR")
                st.error("Erro ao ler planilha")
                return

    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    elif origem == "Site":

        url = st.text_input("URL do site", key="url_site_origem")

        estoque_padrao_site = st.number_input(
            "Estoque padrão quando disponível",
            min_value=0,
            value=10,
            step=1,
            key="estoque_padrao_site",
        )

        if url:

            if st.button("Buscar produtos do site", width="stretch"):

                log_debug(f"Iniciando crawler: {url}")

                progress = st.progress(0)
                status = st.empty()

                try:
                    status.info("🔎 Buscando produtos...")

                    df_origem = executar_crawler(url)

                    progress.progress(50)

                    if df_origem is None or df_origem.empty:
                        st.error("Nenhum produto encontrado")
                        return

                    status.info("🧠 Processando com IA...")

                    df_origem = pd.DataFrame(df_origem)

                    progress.progress(100)
                    status.success("✅ Concluído")

                    st.session_state["df_origem_site"] = df_origem

                except Exception as e:
                    log_debug(f"Erro crawler: {e}", "ERROR")
                    st.error("Erro ao buscar site")
                    return

        df_origem = st.session_state.get("df_origem_site")

    if df_origem is None or df_origem.empty:
        return

    # mantém compatibilidade com seu fluxo
    st.session_state["df_origem"] = df_origem
