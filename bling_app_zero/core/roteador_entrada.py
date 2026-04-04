from typing import List, Optional

import pandas as pd

from ..scrapers.extrator_produto import extrair_produtos_de_urls
from ..scrapers.fetcher import baixar_html
from ..utils.xml_nfe import arquivo_parece_xml_nfe, ler_xml_nfe
from ..utils.excel import ler_planilha, normalizar_colunas, limpar_valores_vazios


ORIGEM_PLANILHA = "planilha"
ORIGEM_XML = "xml_nfe"
ORIGEM_SCRAPER_URL = "scraper_url"


def _padronizar_df(df: pd.DataFrame, origem_tipo: str, origem_ref: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)

    if "origem_tipo" not in df.columns:
        df["origem_tipo"] = origem_tipo

    if "origem_arquivo_ou_url" not in df.columns:
        df["origem_arquivo_ou_url"] = origem_ref

    return df


def carregar_entrada_upload(arquivo) -> pd.DataFrame:
    if arquivo is None:
        return pd.DataFrame()

    if arquivo_parece_xml_nfe(arquivo):
        df = ler_xml_nfe(arquivo)
        return _padronizar_df(df, ORIGEM_XML, getattr(arquivo, "name", "xml_nfe"))

    df = ler_planilha(arquivo)
    return _padronizar_df(df, ORIGEM_PLANILHA, getattr(arquivo, "name", "planilha"))


def carregar_entrada_urls(texto_urls: str) -> pd.DataFrame:
    urls = [
        linha.strip()
        for linha in (texto_urls or "").splitlines()
        if linha.strip()
    ]

    if not urls:
        return pd.DataFrame()

    df = extrair_produtos_de_urls(urls, baixar_html)
    return _padronizar_df(df, ORIGEM_SCRAPER_URL, "lista_urls")


def detectar_modo_visual_por_upload(arquivo) -> str:
    if arquivo is None:
        return ""

    nome = (getattr(arquivo, "name", "") or "").lower().strip()

    if nome.endswith(".xml"):
        return "XML NF-e"
    if nome.endswith(".csv"):
        return "Planilha CSV"
    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return "Planilha Excel"

    return "Arquivo"
