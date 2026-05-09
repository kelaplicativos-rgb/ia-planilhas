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
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def choose_site_model_df(upload, operation: str = 'cadastro') -> pd.DataFrame | None:
    if str(operation or '').strip().lower() == 'estoque':
        return choose_site_estoque_model_df(upload)
    return choose_site_cadastro_model_df(upload)


def requested_columns_for_site_capture(
    operation: str,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> list[str] | None:
    """Retorna somente as colunas do modelo da operação atual.

    Regra BLINGFIX:
    - cadastro por site usa apenas modelo de cadastro;
    - estoque por site usa apenas modelo de estoque;
    - nunca mistura cadastro + estoque na mesma captura;
    - estoque por site não usa fallback solto sem modelo.
    """
    normalized = str(operation or '').strip().lower()
    if normalized == 'estoque':
        columns = unique_columns(columns_from_df(df_modelo_estoque))
    else:
        columns = unique_columns(columns_from_df(df_modelo_cadastro))
    return columns or None


def has_home_site_model_for_operation(operation: str) -> bool:
    normalized = str(operation or '').strip().lower()
    if normalized == 'estoque':
        return isinstance(get_home_estoque_model(), pd.DataFrame)
    return isinstance(get_home_cadastro_model(), pd.DataFrame)


def render_optional_site_model_upload(operation: str = 'cadastro') -> object:
    normalized = str(operation or '').strip().lower()
    operation_key = 'estoque' if normalized == 'estoque' else 'cadastro'

    if has_home_site_model_for_operation(operation_key):
        st.success(f'Modelo de {operation_key} já carregado no passo inicial.')
        st.caption('Este fluxo vai usar o modelo salvo. Não é necessário anexar novamente.')
        return EmptyModelUpload()

    if get_home_cadastro_model() is not None or get_home_estoque_model() is not None:
        st.warning('Existe modelo carregado na Home, mas não para esta operação.')

    required_model = operation_key == 'estoque'
    caption = (
        'Obrigatório para estoque por site: o sistema só vai buscar as colunas existentes neste modelo.'
        if required_model
        else 'Anexe o modelo do Bling para o sistema buscar somente as colunas pedidas.'
    )

    return render_model_upload_box(
        title='Modelo do Bling para esta operação',
        operation=operation_key,
        key=f'model_upload_site_{operation_key}',
        required_model=required_model,
        caption=caption,
    )
