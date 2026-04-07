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
# HELPERS XML / PREVIEW
# ==========================================================
def _somente_digitos(valor) -> str:
    return re.sub(r"\D+", "", str(valor or "").strip())


def _safe_str(valor) -> str:
    try:
        return "" if pd.isna(valor) else str(valor).strip()
    except Exception:
        return ""


def _safe_float(valor, default: float = 0.0) -> float:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return default

        # normalização leve para valores monetários
        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = texto.replace(" ", "")

        if texto.count(",") == 1 and texto.count(".") > 1:
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", ".")

        return float(texto)
    except Exception:
        return default


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """
    Usado para evitar erro do Arrow/Streamlit em previews:
