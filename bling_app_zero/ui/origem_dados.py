import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df,
    safe_df_estrutura,
)


EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}


# =========================
# UTIL
# =========================
def _extensao(upload) -> str:
    nome = str(getattr(upload, "name", "") or "").strip().lower()
    return Path(nome).suffix.lower()


def _eh_excel_familia(ext: str) -> bool:
    return ext in {".csv", ".xlsx", ".xls"}


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    return base


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)


# =========================
# LEITURA CSV / EXCEL
# =========================
def _ler_tabular(upload):
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    dtype=str,
                    encoding="utf-8",
                    engine="python",
                ).fillna("")

                df.columns = [str(c).strip() for c in df.columns if str(c).strip()]

                if len(df.columns) > 0:
                    return df

            except Exception:
                continue

        raise ValueError("Não foi possível ler o CSV.")

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(upload, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns if str(c).strip()]
        return df

    raise ValueError("Arquivo tabular inválido.")


# =========================
# 🔥 LEITURA XML (CORRIGIDO)
# =========================
def _parse_xml_nfe(upload) -> pd.DataFrame:
    try:
        xml_bytes = upload.getvalue()
        root = ET.fromstring(xml_bytes)
    except Exception:
        return pd.DataFrame()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    itens = root.findall(".//nfe:det", ns)

    rows = []

    for det in itens:
        prod = det.find(".//nfe:prod", ns)
        if prod is None:
            continue

        def get(tag):
            el = prod.find(f"nfe:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        gtin = get("cEAN")
        if gtin in {"SEM GTIN", "SEM EAN"}:
            gtin = ""

        rows.append(
            {
                "Código": get("cProd"),
                "Descrição": get("xProd"),
                "NCM": get("NCM"),
                "CFOP": get("CFOP"),
                "Unidade": get("uCom"),
                "Quantidade": get("qCom"),
                "Preço de custo": get("vUnCom"),
                "Valor total": get("vProd"),
                "GTIN": gtin,
            }
        )

    return pd.DataFrame(rows)


# =========================
# PREVIEW
# =========================
def _preview_dataframe(df: pd.DataFrame, titulo: str) -> None:
    st.markdown(f"**{titulo}**")

    if not isinstance(df, pd.DataFrame):
        st.info("Arquivo sem estrutura tabular.")
        return

    if df.empty:
        st.warning("Arquivo sem dados.")
        return

    st.dataframe(df.head(10), use_container_width=True)


# =========================
# PROCESSAMENTO ORIGEM
# =========================
def _processar_upload_origem(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo inválido.")
        return

    # 🔥 CSV / EXCEL
    if _eh_excel_familia(ext):
        df = _normalizar_df(_ler_tabular(upload))

        if not safe_df(df):
            st.error("Planilha vazia.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "tabular")

        st.success("Planilha carregada.")
        _preview_dataframe(df, "Preview da origem")
        return

    # 🔥 XML (AGORA FUNCIONA)
    if ext == ".xml":
        df = _parse_xml_nfe(upload)

        if not safe_df(df):
            st.error("Não foi possível extrair dados do XML.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "xml")

        st.success("XML convertido com sucesso.")
        _preview_dataframe(df, "Preview do XML")
        return

    # PDF (placeholder)
    _guardar_upload_bruto("origem_upload", upload, "documento")
    st.warning("PDF ainda não processado.")


# =========================
# PROCESSAMENTO MODELO
# =========================
def _processar_upload_modelo(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if _eh_excel_familia(ext):
        df = _normalizar_df(_ler_tabular(upload))

        if not safe_df_estrutura(df):
            st.error("Modelo inválido.")
            return

        st.session_state["df_modelo"] = df
        st.success("Modelo carregado.")
        _preview_dataframe(df, "Preview do modelo")
        return


# =========================
# UI PRINCIPAL
# =========================
def render_origem_dados():
    st.subheader("1. Origem dos dados")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastro de Produtos"):
            st.session_state["tipo_operacao"] = "cadastro"

    with col2:
        if st.button("Atualização de Estoque"):
            st.session_state["tipo_operacao"] = "estoque"

    if not st.session_state.get("tipo_operacao"):
        return

    if st.session_state["tipo_operacao"] == "estoque":
        deposito = st.text_input("Nome do depósito")
        st.session_state["deposito_nome"] = deposito

    st.markdown("### Arquivo do fornecedor")
    upload_origem = st.file_uploader("Enviar arquivo")

    if upload_origem:
        _processar_upload_origem(upload_origem)

    st.markdown("### Modelo")
    upload_modelo = st.file_uploader("Enviar modelo")

    if upload_modelo:
        _processar_upload_modelo(upload_modelo)

    if safe_df(st.session_state.get("df_origem")) and safe_df_estrutura(
        st.session_state.get("df_modelo")
    ):
        if st.button("Continuar ➜"):
            ir_para_etapa("precificacao")
