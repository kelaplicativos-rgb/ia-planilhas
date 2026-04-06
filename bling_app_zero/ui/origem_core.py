# bling_app_zero/ui/origem_core.py

import csv
import hashlib
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pandas as pd
from pandas.errors import ParserError


# ==========================================================
# TEXTO / NORMALIZAÇÃO
# ==========================================================
def _normalizar_texto(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _mapa_colunas_normalizadas(colunas: List[str]) -> Dict[str, str]:
    return {_normalizar_texto(col): col for col in colunas}


# ==========================================================
# HASH
# ==========================================================
def _gerar_hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


# ==========================================================
# CONVERSORES
# ==========================================================
def _to_text(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _to_float(valor) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


# ==========================================================
# XML
# ==========================================================
def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _find_child_text(element: ET.Element, child_name: str) -> str:
    for child in list(element):
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def _parse_nfe_xml_produtos(xml_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml_bytes)
    itens = []

    for det in root.iter():
        if _local_name(det.tag) != "det":
            continue

        prod = next((c for c in list(det) if _local_name(c.tag) == "prod"), None)
        if not prod:
            continue

        itens.append({
            "codigo": _find_child_text(prod, "cProd"),
            "gtin": _find_child_text(prod, "cEAN"),
            "descricao": _find_child_text(prod, "xProd"),
            "ncm": _find_child_text(prod, "NCM"),
            "unidade": _find_child_text(prod, "uCom"),
            "quantidade": _find_child_text(prod, "qCom"),
            "preco_custo": _find_child_text(prod, "vUnCom"),
        })

    return _normalizar_colunas(pd.DataFrame(itens))


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _detectar_encoding(raw_bytes: bytes) -> str:
    for enc in ["utf-8", "latin1"]:
        try:
            raw_bytes.decode(enc)
            return enc
        except:
            continue
    return "latin1"


def _detectar_separador(texto: str) -> str:
    return ";" if texto.count(";") > texto.count(",") else ","


def _ler_csv_robusto(arquivo) -> Tuple[pd.DataFrame, str]:
    raw = arquivo.getvalue()
    encoding = _detectar_encoding(raw)
    texto = raw.decode(encoding, errors="replace")
    sep = _detectar_separador(texto)

    df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)
    return _normalizar_colunas(df), "CSV"


# ==========================================================
# LEITURA GERAL
# ==========================================================
def ler_arquivo_upload(arquivo) -> Tuple[pd.DataFrame, str]:
    nome = str(getattr(arquivo, "name", "")).lower()

    if nome.endswith(".xml"):
        return _parse_nfe_xml_produtos(arquivo.getvalue()), "XML"

    if nome.endswith(".csv"):
        return _ler_csv_robusto(arquivo)

    return _normalizar_colunas(pd.read_excel(arquivo, dtype=str)), "Planilha"
