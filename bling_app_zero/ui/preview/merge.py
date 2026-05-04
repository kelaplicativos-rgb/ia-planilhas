from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.app_helpers import safe_df_estrutura


def valor_preenchido(valor) -> bool:
    if pd.isna(valor):
        return False
    if isinstance(valor, str):
        return valor.strip() != ""
    return True


def mesclar_preservando_manual(df_base: pd.DataFrame, df_manual: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(df_manual, pd.DataFrame) or not safe_df_estrutura(df_manual):
        return df_base.copy()
    if df_base is None or df_base.empty:
        return df_manual.copy().fillna("")
    base = df_base.copy().fillna("")
    manual = df_manual.copy().fillna("")
    if len(manual.index) != len(base.index):
        return base
    for col in base.columns:
        if col not in manual.columns:
            manual[col] = ""
    manual = manual[base.columns.tolist()]
    for col in base.columns:
        mask = manual[col].apply(valor_preenchido)
        base.loc[mask, col] = manual.loc[mask, col]
    return base
