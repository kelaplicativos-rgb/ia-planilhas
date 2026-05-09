from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model
from bling_app_zero.ui.model_upload import render_model_upload_box


@dataclass
class EmptyModelUpload:
    cadastro_model_df: pd.DataFrame | None = None
    estoque_model_df: pd.DataFrame | None = None
    model_df: pd.DataFrame | None = None


def unique_columns(columns: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for column in columns:
        text = str(column or '').strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def columns_from_df(df: pd.DataFrame | None) -> list[str]:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return [str(c) for c in df.columns]
    return []


def choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        return upload.estoque_model_df
    return None


def choose_site_model_df(upload) -> pd.DataFrame | None:
    return choose_site_cadastro_model_df(upload)


def requested_columns_for_site_capture(
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> list[str] | None:
    merged = unique_columns(columns_from_df(df_modelo_cadastro) + columns_from_df(df_modelo_estoque))
    return merged or None


def render_optional_site_model_upload() -> object:
    if get_home_cadastro_model() is not None or get_home_estoque_model() is not None:
        st.success('Modelos do Bling já carregados no passo inicial.')
        st.caption('Este fluxo vai usar os modelos salvos. Não é necessário anexar novamente.')
        return EmptyModelUpload()

    return render_model_upload_box(
        title='Modelos para cadastro e estoque',
        operation='cadastro',
        key='model_upload_site',
        required_model=False,
        caption='Anexe os modelos do Bling para preencher as colunas certas.',
    )
