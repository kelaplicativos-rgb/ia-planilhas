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


def processar_upload_planilha(arquivo) -> tuple[pd.DataFrame | None, dict]:
    nome = nome_arquivo(arquivo)
    hash_ref = hash_arquivo_upload(arquivo)

    df = ler_planilha(arquivo)

    if not safe_df_com_linhas(df):
        return None, {
            "tipo": "planilha",
            "nome": nome,
            "hash": hash_ref,
            "erro": "Erro ao ler planilha",
        }

    return normalizar_df(df), {
        "tipo": "planilha",
        "nome": nome,
        "hash": hash_ref,
    }


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


def processar_upload_xml(arquivo) -> tuple[pd.DataFrame | None, dict]:
    nome = nome_arquivo(arquivo)
    hash_ref = hash_arquivo_upload(arquivo)

    try:
        arquivo.seek(0)
        conteudo_raw = arquivo.read()
        if isinstance(conteudo_raw, bytes):
            conteudo = conteudo_raw.decode("utf-8", errors="ignore")
        else:
            conteudo = str(conteudo_raw or "")
    except Exception:
        return None, {
            "tipo": "xml",
            "nome": nome,
            "hash": hash_ref,
            "erro": "Erro ao ler XML",
        }

    try:
        root = ET.fromstring(conteudo)
    except Exception:
        return None, {
            "tipo": "xml",
            "nome": nome,
            "hash": hash_ref,
            "erro": "XML inválido",
        }

    itens = []

    for det in root.iter():
        if _local_name(det.tag).lower() != "det":
            continue

        prod = None
        for c in det:
            if _local_name(c.tag).lower() == "prod":
                prod = c
                break

        if prod is None:
            continue

        item = {
            "Código": _find_child_text(prod, "cProd"),
            "Descrição": _find_child_text(prod, "xProd"),
            "Unidade": _find_child_text(prod, "uCom"),
            "Quantidade": _find_child_text(prod, "qCom"),
            "Preço": _find_child_text(prod, "vUnCom"),
            "NCM": _find_child_text(prod, "NCM"),
            "GTIN": _find_child_text(prod, "cEAN"),
            "GTIN tributário": _find_child_text(prod, "cEANTrib"),
            "CFOP": _find_child_text(prod, "CFOP"),
        }

        if any(str(v).strip() for v in item.values()):
            itens.append(item)

    if itens:
        df = pd.DataFrame(itens)
        return normalizar_df(df), {
            "tipo": "xml",
            "nome": nome,
            "hash": hash_ref,
            "texto_bruto": conteudo,
        }

    df = pd.DataFrame(
        [
            {
                "Arquivo": nome,
                "Tipo": "XML",
                "Conteúdo XML": conteudo[:5000],
            }
        ]
    )

    return normalizar_df(df), {
        "tipo": "xml",
        "nome": nome,
        "hash": hash_ref,
        "texto_bruto": conteudo,
    }


def extrair_texto_pdf(arquivo) -> str:
    try:
        arquivo.seek(0)
        conteudo = arquivo.read()
        if not conteudo:
            return ""

        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(BytesIO(conteudo))
            return "\n".join((pagina.extract_text() or "") for pagina in reader.pages).strip()
        except Exception:
            pass

        try:
            import PyPDF2  # type: ignore

            reader = PyPDF2.PdfReader(BytesIO(conteudo))
            return "\n".join((pagina.extract_text() or "") for pagina in reader.pages).strip()
        except Exception:
            return ""
    except Exception:
        return ""


def processar_upload_pdf(arquivo) -> tuple[pd.DataFrame | None, dict]:
    nome = nome_arquivo(arquivo)
    hash_ref = hash_arquivo_upload(arquivo)
    texto = extrair_texto_pdf(arquivo)

    if not texto:
        return None, {
            "tipo": "pdf",
            "nome": nome,
            "hash": hash_ref,
            "erro": "Erro ao ler PDF",
        }

    df = pd.DataFrame(
        [
            {
                "Arquivo": nome,
                "Tipo": "PDF",
                "Texto PDF": texto[:5000],
            }
        ]
    )

    return normalizar_df(df), {
        "tipo": "pdf",
        "nome": nome,
        "hash": hash_ref,
        "texto_bruto": texto,
    }


def processar_upload_arquivo_unificado(uploaded_file):
    if uploaded_file is None:
        return None, {
            "tipo": "",
            "nome": "",
            "hash": "",
            "erro": "Arquivo ausente",
        }

    tipo = detectar_tipo_origem_por_arquivo(uploaded_file)

    if tipo == "planilha":
        return processar_upload_planilha(uploaded_file)

    if tipo == "xml":
        return processar_upload_xml(uploaded_file)

    if tipo == "pdf":
        return processar_upload_pdf(uploaded_file)

    return None, {
        "tipo": "",
        "nome": nome_arquivo(uploaded_file),
        "hash": hash_arquivo_upload(uploaded_file),
        "erro": "Formato não suportado",
    }
