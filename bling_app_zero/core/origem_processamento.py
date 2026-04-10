from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd


EXTENSOES_PLANILHA = {"xlsx", "xls", "xlsb", "csv"}
EXTENSOES_SUPORTADAS_ORIGEM = {"xlsx", "xls", "xlsb", "csv", "xml", "pdf"}


def nome_arquivo(uploaded_file: Any) -> str:
    try:
        return str(getattr(uploaded_file, "name", "") or "").strip()
    except Exception:
        return ""


def extensao_arquivo(uploaded_file: Any) -> str:
    nome = nome_arquivo(uploaded_file).lower()
    if "." not in nome:
        return ""
    return nome.rsplit(".", 1)[-1]


def hash_arquivo_upload(uploaded_file: Any) -> str:
    try:
        if uploaded_file is None:
            return ""
        pos = uploaded_file.tell()
        uploaded_file.seek(0)
        conteudo = uploaded_file.read()
        uploaded_file.seek(pos)

        if not isinstance(conteudo, (bytes, bytearray)):
            conteudo = str(conteudo).encode("utf-8", errors="ignore")

        return hashlib.sha1(conteudo).hexdigest()
    except Exception:
        return ""


def detectar_tipo_origem_por_arquivo(uploaded_file: Any) -> str:
    ext = extensao_arquivo(uploaded_file)

    if ext in EXTENSOES_PLANILHA:
        return "planilha"
    if ext == "xml":
        return "xml"
    if ext == "pdf":
        return "pdf"
    return ""


def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]
        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")
        return df
    except Exception:
        return df


def safe_df_com_linhas(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def safe_df_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def ler_planilha(uploaded_file: Any) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    nome = nome_arquivo(uploaded_file).lower()

    try:
        if nome.endswith(".csv"):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="utf-8")

        if nome.endswith(".xlsb"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine="pyxlsb")

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file)

        return None
    except Exception:
        return None


def ler_modelo(uploaded_file: Any) -> pd.DataFrame | None:
    df = ler_planilha(uploaded_file)
    if not safe_df_estrutura(df):
        return None
    return normalizar_df(df)


def _local_name(tag: str) -> str:
    try:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return str(tag or "")
    except Exception:
        return str(tag or "")


def _find_child_text(node: ET.Element, child_name: str) -> str:
    try:
        for child in list(node):
            if _local_name(child.tag).lower() == child_name.lower():
                return str(child.text or "").strip()
    except Exception:
        pass
    return ""


def processar_upload_planilha(arquivo: Any) -> tuple[pd.DataFrame | None, dict]:
    nome = nome_arquivo(arquivo)
    hash_ref = hash_arquivo_upload(arquivo)

    df = ler_planilha(arquivo)
