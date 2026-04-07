from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados, tem_upload_ativo
from bling_app_zero.ui.origem_dados_helpers import ler_planilha_segura, log_debug
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


_EXTENSOES_PLANILHA_PERMITIDAS = {".xlsx", ".xls", ".csv", ".xlsm", ".xlsb"}
_EXTENSOES_XML_PERMITIDAS = {".xml"}


# ==========================================================
# HELPERS XML IA 🔥
# ==========================================================
def _somente_digitos(valor) -> str:
    return re.sub(r"\D+", "", str(valor or "").strip())


def _safe_str(valor) -> str:
    try:
        return "" if pd.isna(valor) else str(valor).strip()
    except Exception:
        return ""


def _safe_float(valor, default=0.0) -> float:
    try:
        texto = str(valor or "").strip()
        texto = texto.replace(".", "").replace(",", ".") if texto.count(",") == 1 and texto.count(".") > 1 else texto
        texto = texto.replace(",", ".")
        return float(texto)
    except Exception:
        return default


def _normalizar_df_xml(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()

        # 🔥 CONVERTE TUDO PRA STRING (ANTI-CRASH STREAMLIT)
        for col in df.columns:
            df[col] = df[col].apply(_safe_str)

        df = df.replace({"nan": "", "None": "", "<NA>": ""})

        cols = {str(c).strip().lower(): c for c in df.columns}

        # Código
        for nome in ["código", "codigo", "sku", "referencia"]:
            if nome in cols:
                col = cols[nome]
                df[col] = df[col].apply(lambda x: x.replace(".0", ""))

        # GTIN / EAN
        for nome in ["gtin", "ean", "codigo de barras", "código de barras"]:
            if nome in cols:
                col = cols[nome]
                df[col] = df[col].apply(_somente_digitos)

        # NCM
        if "ncm" in cols:
            df[cols["ncm"]] = df[cols["ncm"]].apply(_somente_digitos)

        # Preço
        for nome in ["valor", "preço", "preco", "valor unitario", "valor unitário"]:
            if nome in cols:
                col = cols[nome]
                df["preco_compra_xml"] = df[col].apply(_safe_float)
                break

        return df
    except Exception:
        return df


def _limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        for col in df.columns:
            nome = str(col).lower()
            if "gtin" in nome or "ean" in nome:
                df[col] = df[col].apply(
                    lambda x: x if len(_somente_digitos(x)) in [8, 12, 13, 14] else ""
                )
        return df
    except Exception:
        return df


# ==========================================================
# RESTANTE DO ARQUIVO (SEU FLUXO ORIGINAL)
# ==========================================================

def nome_arquivo(arquivo) -> str:
    try:
        return str(getattr(arquivo, "name", "") or "").strip()
    except Exception:
        return ""


def extensao_arquivo(arquivo) -> str:
    try:
        return Path(nome_arquivo(arquivo)).suffix.lower().strip()
    except Exception:
        return ""


def arquivo_planilha_permitido(arquivo) -> bool:
    return extensao_arquivo(arquivo) in _EXTENSOES_PLANILHA_PERMITIDAS


def arquivo_xml_permitido(arquivo) -> bool:
    return extensao_arquivo(arquivo) in _EXTENSOES_XML_PERMITIDAS


def texto_extensoes_planilha() -> str:
    return ", ".join(sorted(_EXTENSOES_PLANILHA_PERMITIDAS))


def hash_arquivo_upload(arquivo) -> str:
    try:
        if arquivo is None:
            return ""

        nome = nome_arquivo(arquivo)
        size = getattr(arquivo, "size", None)

        if hasattr(arquivo, "seek"):
            arquivo.seek(0)

        conteudo = arquivo.getvalue() if hasattr(arquivo, "getvalue") else arquivo.read()

        if hasattr(arquivo, "seek"):
            arquivo.seek(0)

        base = f"{nome}|{size}|".encode("utf-8") + conteudo
        return hashlib.md5(base).hexdigest()
    except Exception:
        return ""


# ==========================================================
# 🔥 CORREÇÃO PRINCIPAL AQUI
# ==========================================================
def ler_origem_xml(arquivo_xml):
    if arquivo_xml is None:
        return None

    if not arquivo_xml_permitido(arquivo_xml):
        st.error("Envie um arquivo XML válido (.xml).")
        return None

    try:
        if not arquivo_parece_xml_nfe(arquivo_xml):
            st.error("O arquivo anexado não parece ser um XML de NFe válido.")
            return None

        df_xml = ler_xml_nfe(arquivo_xml)

        if not safe_df_dados(df_xml):
            st.error("Não foi possível extrair dados do XML.")
            return None

        # 🔥🔥🔥 NÍVEL IA AQUI
        df_xml = _normalizar_df_xml(df_xml)
        df_xml = _limpar_gtin_invalido(df_xml)

        st.session_state["df_origem_xml"] = df_xml.copy()

        log_debug(
            f"XML tratado com IA: {getattr(arquivo_xml, 'name', 'arquivo_xml')} "
            f"({len(df_xml)} linhas)"
        )

        return df_xml

    except Exception as e:
        log_debug(f"Erro ao ler XML: {e}", "ERRO")
        st.error("Não foi possível ler o XML.")
        return None


# (resto do arquivo continua igual)
