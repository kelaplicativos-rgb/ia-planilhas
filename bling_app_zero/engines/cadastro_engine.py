from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_models import cadastro_default_model, enforce_model_contract
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping, auto_map_columns

DEFAULT_CADASTRO_COLUMNS = list(cadastro_default_model().columns)


def default_model() -> pd.DataFrame:
    return cadastro_default_model()


def run_cadastro_engine(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    model = df_model.copy().fillna('') if isinstance(df_model, pd.DataFrame) and len(df_model.columns) else default_model()
    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    mapping = auto_map_columns(source, model)
    final = apply_mapping(source, model, mapping)
    final = enforce_model_contract(final, 'cadastro', model)
    return sanitize_for_bling(final, operation='cadastro'), mapping