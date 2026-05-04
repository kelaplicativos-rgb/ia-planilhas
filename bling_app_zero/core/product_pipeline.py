from __future__ import annotations

from typing import Optional

import pandas as pd

from bling_app_zero.core.product_normalizer import normalize_to_product_master
from bling_app_zero.core.product_validator import validate_product_master


def build_product_master(
    df: pd.DataFrame,
    origem: str = "",
    fornecedor: str = "",
    deposito: str = "",
    preco_calculado_col: Optional[str] = None,
) -> pd.DataFrame:
    master = normalize_to_product_master(
        df=df,
        origem=origem,
        fornecedor=fornecedor,
        deposito=deposito,
        preco_calculado_col=preco_calculado_col,
    )
    return validate_product_master(master)


def choose_best_source_df(session_state) -> pd.DataFrame:
    for key in ["df_precificado", "df_origem", "df_saida", "df_final"]:
        value = session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy()
    return pd.DataFrame()
