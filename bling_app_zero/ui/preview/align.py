from __future__ import annotations

import pandas as pd


def colunas_iguais_ao_modelo(df_final: pd.DataFrame, df_modelo: pd.DataFrame) -> bool:
    if not isinstance(df_final, pd.DataFrame) or not isinstance(df_modelo, pd.DataFrame):
        return False
    return [str(c).strip() for c in df_final.columns.tolist()] == [str(c).strip() for c in df_modelo.columns.tolist()]


def alinhar_ao_modelo_bling(df_final: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    cols = [str(c).strip() for c in df_modelo.columns.tolist()]
    base = df_final.copy().fillna("") if isinstance(df_final, pd.DataFrame) else pd.DataFrame()
    if base.empty and cols:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in base.columns:
            base[col] = ""
    return base[cols].fillna("")
