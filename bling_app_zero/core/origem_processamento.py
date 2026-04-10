from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd


EXTENSOES_PLANILHA = {"xlsx", "xls", "xlsb", "csv"}


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


def processar_upload_planilha(arquivo) -> tuple[pd.DataFrame | None, dict]:
    nome = nome_arquivo(arquivo)
    hash_ref = hash_arquivo_upload(arquivo)

    df = ler_planilha(arquivo)

    if not safe_df_com_linhas(df):
        return None, {"erro": "Erro ao ler planilha"}

    return normalizar_df(df), {
        "tipo": "planilha",
        "nome": nome,
        "hash": hash_ref,
    }


def processar_upload_xml(arquivo) -> tuple[pd.DataFrame | None, dict]:
    try:
        arquivo.seek(0)
        conteudo = arquivo.read().decode("utf-8", errors="ignore")
    except Exception:
        return None, {"erro": "Erro ao ler XML"}

    try:
        root = ET.fromstring(conteudo)
    except Exception:
        return None, {"erro": "XML inválido"}

    itens = []

    for det in root.iter():
        if "det" in det.tag:
            prod = None
            for c in det:
                if "prod" in c.tag:
                    prod = c
                    break

            if prod is None:
                continue

            item = {}
            for c in prod:
                item[c.tag.split("}")[-1]] = c.text

            itens.append(item)

    if not itens:
        return None, {"erro": "Nenhum item encontrado no XML"}

    df = pd.DataFrame(itens)

    return normalizar_df(df), {
        "tipo": "xml",
        "nome": nome_arquivo(arquivo),
        "hash": hash_arquivo_upload(arquivo),
    }


def extrair_texto_pdf(arquivo) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(arquivo.read()))
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception:
        return ""


def processar_upload_pdf(arquivo) -> tuple[pd.DataFrame | None, dict]:
    texto = extrair_texto_pdf(arquivo)

    if not texto:
        return None, {"erro": "Erro ao ler PDF"}

    df = pd.DataFrame([{"Texto": texto[:5000]}])

    return df, {
        "tipo": "pdf",
        "nome": nome_arquivo(arquivo),
        "hash": hash_arquivo_upload(arquivo),
    }


def processar_upload_arquivo_unificado(uploaded_file):
    tipo = detectar_tipo_origem_por_arquivo(uploaded_file)

    if tipo == "planilha":
        return processar_upload_planilha(uploaded_file)

    if tipo == "xml":
        return processar_upload_xml(uploaded_file)

    if tipo == "pdf":
        return processar_upload_pdf(uploaded_file)

    return None, {"erro": "Formato não suportado"}
