from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_models import ESTOQUE_BLING_COLUMNS, estoque_default_model, model_columns

DEFAULT_ESTOQUE_COLUMNS = list(ESTOQUE_BLING_COLUMNS)


def default_model() -> pd.DataFrame:
    return estoque_default_model()


def requested_columns_from_model(df_model: pd.DataFrame | None) -> list[str]:
    return model_columns(df_model, 'estoque')