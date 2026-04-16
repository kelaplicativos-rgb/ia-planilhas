
from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.app_dataframe import garantir_dataframe


def dataframe_para_csv_bytes(df: pd.DataFrame) -> bytes:
    base = garantir_dataframe(df).fillna("")
    csv_texto = base.to_csv(index=False, sep=";")
    return csv_texto.encode("utf-8-sig")

