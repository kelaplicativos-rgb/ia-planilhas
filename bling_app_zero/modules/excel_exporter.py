from __future__ import annotations

import pandas as pd
from io import BytesIO


def exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Exporta DataFrame exatamente no formato esperado pelo Bling.
    NÃO altera dados, apenas converte para Excel.
    """

    if df is None or df.empty:
        raise ValueError("DataFrame vazio para exportação.")

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    buffer.seek(0)
    return buffer.read()
