from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


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


def _normalizar_gtin(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = "".join(ch for ch in texto if ch.isdigit())

    if len(texto) in (8, 12, 13, 14):
        return texto

    return ""


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if "gtin" in str(col).lower() or "ean" in str(col).lower():
            df[col] = df[col].apply(_normalizar_gtin)
    return df


def _ler_csv_seguro(arquivo):
    try:
        return pd.read_csv(arquivo)
    except:
        try:
            return pd.read_csv(arquivo, sep=";")
        except:
            return pd.read_csv(arquivo, engine="python", on_bad_lines="skip")


def _gerar_sugestoes(df_origem, colunas_modelo):
    try:
        return sugestao_automatica(df_origem, colunas_modelo)
    except:
        try:
            return sugestao_automatica(df_origem)
        except:
            return {}


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

    # =========================
    # INPUT
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "csv"],
        )

        if arquivo:
            if arquivo.name.endswith(".csv"):
                df_origem = _ler_csv_seguro(arquivo)
            else:
                df_origem = pd.read_excel(arquivo)

    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    elif origem == "Site":
        url = st.text_input("URL do site")

        # 🔥 NOVO CAMPO
        estoque_padrao_site = st.number_input(
            "Estoque padrão quando disponível",
            min_value=0,
            value=10,
            step=1,
        )

        if url:
            st.info("Captura em andamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    # =========================
    # MODO
    # =========================
    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
    )

    modelo = st.file_uploader("Modelo", type=["xlsx"])

    if not modelo:
        st.warning("Anexe o modelo.")
        return

    df_modelo = pd.read_excel(modelo)
    colunas_modelo = list(df_modelo.columns)

    sugestoes = _gerar_sugestoes(df_origem, colunas_modelo)

    if "mapeamento_manual" not in st.session_state:
        st.session_state["mapeamento_manual"] = sugestoes

    mapa = st.session_state["mapeamento_manual"]

    st.markdown("### Preview origem")
    st.dataframe(_safe_preview(df_origem), use_container_width=True)

    st.markdown("### Mapeamento")

    if st.button("Limpar mapeamento"):
        st.session_state["mapeamento_manual"] = {}
        st.rerun()

    opcoes = [""] + list(df_origem.columns)

    for col in colunas_modelo:
        mapa[col] = st.selectbox(
            col,
            opcoes,
            index=opcoes.index(mapa.get(col, "")) if mapa.get(col, "") in opcoes else 0,
            key=f"map_{col}",
        )

    # =========================
    # ESTOQUE
    # =========================
    deposito = ""
    if modo == "estoque":
        deposito = st.text_input("Nome do depósito (obrigatório)")

    # =========================
    # MONTAGEM
    # =========================
    def montar_df():
        df_saida = pd.DataFrame(index=df_origem.index)

        for col in colunas_modelo:
            origem_col = mapa.get(col)

            if origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        # 🔥 REGRA ESTOQUE SITE
        if origem == "Site":
            for col in df_saida.columns:
                if "estoque" in col.lower():

                    def definir_estoque(valor):
                        texto = str(valor).lower()

                        if "esgotado" in texto or "indisponivel" in texto:
                            return 0

                        if texto.strip() == "" or texto == "nan":
                            return estoque_padrao_site

                        try:
                            return int(float(valor))
                        except:
                            return estoque_padrao_site

                    df_saida[col] = df_saida[col].apply(definir_estoque)

        # 🔥 DEPÓSITO
        if modo == "estoque":
            if not deposito:
                return None

            for col in df_saida.columns:
                if "deposito" in col.lower():
                    df_saida[col] = deposito

        df_saida = _limpar_gtin(df_saida)

        return df_saida

    st.markdown("### Preview saída")

    df_preview = montar_df()

    if modo == "estoque" and not deposito:
        st.warning("Informe o depósito")
    elif df_preview is not None:
        st.dataframe(_safe_preview(df_preview), use_container_width=True)

    df_final = montar_df()

    if df_final is not None:
        st.session_state["df_final"] = df_final.copy()

        excel = _exportar_df_exato_para_excel_bytes(df_final)

        st.download_button(
            "Baixar",
            data=excel,
            file_name="arquivo.xlsx",
        )
