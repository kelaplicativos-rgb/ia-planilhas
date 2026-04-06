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


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if "gtin" in col.lower():
            df[col] = df[col].astype(str)
            df[col] = df[col].apply(
                lambda x: x if x.isdigit() and len(x) in [8, 12, 13, 14] else ""
            )
    return df


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
            key="upload_planilha_origem",
        )
        if arquivo:
            try:
                if arquivo.name.lower().endswith(".csv"):
                    df_origem = pd.read_csv(arquivo)
                else:
                    df_origem = pd.read_excel(arquivo)
            except Exception as e:
                st.error(f"Erro ao ler planilha: {e}")
                return

    elif origem == "XML":
        arquivo = st.file_uploader(
            "Envie o XML",
            type=["xml"],
            key="upload_xml_origem",
        )
        if arquivo:
            st.warning("Leitura de XML em processamento...")
            return

    elif origem == "Site":
        url = st.text_input("URL do site", key="url_site_origem")
        if url:
            st.info("Captura do site em processamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    origem_hash = _hash_df(df_origem)

    # RESET MAPEAMENTO SE MUDAR PLANILHA
    if st.session_state.get("origem_hash") != origem_hash:
        st.session_state["origem_hash"] = origem_hash
        st.session_state["mapeamento_manual"] = {}
        st.session_state["df_final"] = None

    # =========================
    # MODO
    # =========================
    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
        key="modo_operacao_origem",
    )

    # =========================
    # MODELOS
    # =========================
    modelo_cadastro = None
    modelo_estoque = None

    if modo == "cadastro":
        modelo_cadastro = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx"],
            key="upload_modelo_cadastro",
        )
    else:
        modelo_estoque = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx"],
            key="upload_modelo_estoque",
        )

    if modo == "cadastro" and modelo_cadastro:
        try:
            df_modelo = pd.read_excel(modelo_cadastro)
        except Exception as e:
            st.error(f"Erro ao ler modelo de cadastro: {e}")
            return
    elif modo == "estoque" and modelo_estoque:
        try:
            df_modelo = pd.read_excel(modelo_estoque)
        except Exception as e:
            st.error(f"Erro ao ler modelo de estoque: {e}")
            return
    else:
        st.warning("Anexe o modelo correspondente.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    # =========================
    # MAPEAMENTO
    # =========================
    sugestoes = sugestao_automatica(df_origem, colunas_modelo_ativas)

    if (
        "mapeamento_manual" not in st.session_state
        or not st.session_state["mapeamento_manual"]
    ):
        st.session_state["mapeamento_manual"] = sugestoes or {}

    mapa = st.session_state["mapeamento_manual"]

    st.markdown("### Preview origem")
    st.dataframe(_safe_preview(df_origem), width="stretch")

    st.markdown("### Mapeamento")

    if st.button("Limpar mapeamento", width="stretch"):
        st.session_state["mapeamento_manual"] = {}
        st.rerun()

    opcoes = [""] + list(df_origem.columns)

    for col in colunas_modelo_ativas:
        valor = mapa.get(col, "")
        if valor not in opcoes:
            valor = ""

        mapa[col] = st.selectbox(
            col,
            opcoes,
            index=opcoes.index(valor),
            key=f"map_{col}",
        )

    # =========================
    # ESTOQUE
    # =========================
    deposito = ""
    if modo == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            key="nome_deposito_estoque",
        )

    # =========================
    # MONTAGEM
    # =========================
    def montar_df():
        df_saida = pd.DataFrame()

        for col in colunas_modelo_ativas:
            origem_col = mapa.get(col)

            if origem_col and origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        if modo == "estoque":
            if not deposito:
                return None

            if "Depósito" in df_saida.columns:
                df_saida["Depósito"] = deposito

        df_saida = _limpar_gtin(df_saida)

        return df_saida

    st.divider()
    st.markdown("### Preview saída")

    df_preview = montar_df()
    if modo == "estoque" and not deposito:
        st.warning("Informe o nome do depósito para gerar a planilha de estoque.")
    elif df_preview is not None:
        st.dataframe(_safe_preview(df_preview), width="stretch")

    # =========================
    # DOWNLOAD
    # =========================
    df_final = montar_df()

    if df_final is not None:
        # SALVA O DF FINAL PARA A ABA DE ENVIO USAR,
        # SEM INTERFERIR NO DOWNLOAD
        st.session_state["df_final"] = df_final.copy()

        excel = _exportar_df_exato_para_excel_bytes(df_final)
        nome = "cadastro.xlsx" if modo == "cadastro" else "estoque.xlsx"

        st.download_button(
            "Baixar arquivo",
            data=excel,
            file_name=nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.session_state["df_final"] = None
