from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.engines.cadastro_engine import default_model as cadastro_default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model
from bling_app_zero.ui.estoque_wizard_state import stock_confidence, stock_mapping
from bling_app_zero.ui.mapping_cadastro_flow import render_manual_mapping
from bling_app_zero.ui.mapping_estoque_flow import render_manual_stock_mapping
from bling_app_zero.ui.mapping_review_panel import render_mapping_review_panel


def _model_columns(df_modelo: pd.DataFrame | None, operation: str) -> list[str]:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return [str(column) for column in df_modelo.columns]
    if operation == 'estoque':
        return [str(column) for column in estoque_default_model().columns]
    return [str(column) for column in cadastro_default_model().columns]


def render_shared_cadastro_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    render_manual_mapping(df_source, df_modelo)
    render_mapping_review_panel(
        operation='cadastro',
        mapping=st.session_state.get('mapping_cadastro'),
        confidence=st.session_state.get('mapping_confidence_cadastro'),
        df_source=df_source,
        target_columns=_model_columns(df_modelo, 'cadastro'),
    )


def render_shared_stock_mapping(
    df_source: pd.DataFrame,
    df_modelo_estoque: pd.DataFrame | None,
    deposito: str,
) -> None:
    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)
    render_mapping_review_panel(
        operation='estoque',
        mapping=stock_mapping(),
        confidence=stock_confidence(),
        df_source=df_source,
        target_columns=_model_columns(df_modelo_estoque, 'estoque'),
    )


__all__ = [
    'render_shared_cadastro_mapping',
    'render_shared_stock_mapping',
]
