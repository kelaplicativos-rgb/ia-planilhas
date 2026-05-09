from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_model_for_operation
from bling_app_zero.ui.home_models import get_home_estoque_model, save_home_models
from bling_app_zero.ui.home_shared import show_contract


def home_estoque_model_loaded() -> bool:
    return get_home_estoque_model() is not None


def select_estoque_model(upload) -> pd.DataFrame | None:
    df_modelo_site = get_site_model_for_operation('estoque')
    if isinstance(df_modelo_site, pd.DataFrame):
        return df_modelo_site

    df_modelo_home = get_home_estoque_model()
    if isinstance(df_modelo_home, pd.DataFrame):
        return df_modelo_home

    if isinstance(upload.estoque_model_df, pd.DataFrame):
        save_home_models(None, upload.estoque_model_df)
        return upload.estoque_model_df

    if isinstance(upload.model_df, pd.DataFrame):
        save_home_models(None, upload.model_df)
        return upload.model_df

    return None


def render_estoque_model_contract(df_modelo: pd.DataFrame | None) -> None:
    if isinstance(df_modelo, pd.DataFrame):
        show_contract([str(c) for c in df_modelo.columns])
