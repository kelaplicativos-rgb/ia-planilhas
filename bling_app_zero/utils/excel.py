from __future__ import annotations

from typing import Any

import pandas as pd

# ==========================================================
# IMPORTS COM BLINDAGEM (CRÍTICO)
# ==========================================================
try:
    from .excel_exportacao import (
        df_to_excel_bytes,
        exportar_dataframe_para_excel,
        exportar_df_exato_para_excel_bytes,
        exportar_excel_bytes,
        gerar_zip_com_arquivos,
        gerar_zip_processamento,
    )
except Exception:
    df_to_excel_bytes = None
    exportar_dataframe_para_excel = None
    exportar_df_exato_para_excel_bytes = None
    exportar_excel_bytes = None
    gerar_zip_com_arquivos = None
    gerar_zip_processamento = None


try:
    from .excel_helpers import limpar_gtin_invalido, validar_campos_obrigatorios
except Exception:
    def limpar_gtin_invalido(df):
        return df

    def validar_campos_obrigatorios(df):
        return True, []


try:
    from .excel_leitura import ler_planilha_excel, ler_planilha_segura
except Exception:
    def ler_planilha_excel(*args, **kwargs):
        return pd.DataFrame()

    def ler_planilha_segura(*args, **kwargs):
        return pd.DataFrame()


try:
    from .excel_logs import baixar_logs_txt, log_debug
except Exception:
    def log_debug(msg: str, nivel: str = "INFO"):
        pass

    def baixar_logs_txt():
        return b""


# ==========================================================
# SAFE DF
# ==========================================================
def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# EXPORT (FALLBACK CRÍTICO)
# ==========================================================
def exportar_excel_bytes_seguro(df: pd.DataFrame):
    try:
        if callable(exportar_excel_bytes):
            return exportar_excel_bytes(df)
    except Exception:
        pass

    # fallback simples
    try:
        from io import BytesIO

        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()
    except Exception:
        return b""


# ==========================================================
# EXPORTS
# ==========================================================
__all__ = [
    "log_debug",
    "baixar_logs_txt",
    "limpar_gtin_invalido",
    "validar_campos_obrigatorios",
    "ler_planilha_segura",
    "ler_planilha_excel",
    "safe_df_dados",
    "df_to_excel_bytes",
    "exportar_df_exato_para_excel_bytes",
    "exportar_dataframe_para_excel",
    "exportar_excel_bytes",
    "exportar_excel_bytes_seguro",
    "gerar_zip_com_arquivos",
    "gerar_zip_processamento",
]
