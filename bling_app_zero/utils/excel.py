from __future__ import annotations

from typing import Any

import pandas as pd

from .excel_exportacao import (
    df_to_excel_bytes,
    exportar_dataframe_para_excel,
    exportar_df_exato_para_excel_bytes,
    exportar_excel_bytes,
    gerar_zip_com_arquivos,
    gerar_zip_processamento,
)
from .excel_helpers import limpar_gtin_invalido, validar_campos_obrigatorios
from .excel_leitura import ler_planilha_excel, ler_planilha_segura
from .excel_logs import baixar_logs_txt, log_debug


def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


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
    "gerar_zip_com_arquivos",
    "gerar_zip_processamento",
]
