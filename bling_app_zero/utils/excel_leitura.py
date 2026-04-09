from __future__ import annotations

from typing import Any
from io import BytesIO

import pandas as pd


# ==========================================================
# LEITURA ROBUSTA DE EXCEL
# ==========================================================
def ler_excel_robusto(arquivo: Any) -> pd.DataFrame:
    """
    Lê arquivos Excel de forma resiliente sem quebrar o fluxo.
    Nunca retorna None.
    """

    try:
        if arquivo is None:
            return pd.DataFrame()

        # 🔥 garantir leitura em memória
        if hasattr(arquivo, "read"):
            conteudo = arquivo.read()
            arquivo_bytes = BytesIO(conteudo)
        else:
            arquivo_bytes = arquivo

        nome = str(getattr(arquivo, "name", "")).lower()

        # ==================================================
        # LEITURA POR TIPO
        # ==================================================
        if nome.endswith(".xlsb"):
            df = pd.read_excel(arquivo_bytes, engine="pyxlsb")
        elif nome.endswith(".xls"):
            df = pd.read_excel(arquivo_bytes, engine="xlrd")
        else:
            df = pd.read_excel(arquivo_bytes, engine="openpyxl")

        # ==================================================
        # LIMPEZA
        # ==================================================
        if df is None:
            return pd.DataFrame()

        # remover colunas completamente vazias
        df = df.dropna(axis=1, how="all")

        # remover linhas completamente vazias
        df = df.dropna(axis=0, how="all")

        # garantir colunas como string
        df.columns = [str(c).strip() for c in df.columns]

        # reset index
        df = df.reset_index(drop=True)

        return df

    except Exception:
        # 🔥 nunca quebra o sistema
        return pd.DataFrame()


# ==========================================================
# VALIDAÇÃO SIMPLES
# ==========================================================
def excel_valido(df: pd.DataFrame | None) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False
