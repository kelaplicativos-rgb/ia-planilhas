from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def _df_or_none(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def _upload_attr(upload: Any, name: str) -> pd.DataFrame | None:
    return _df_or_none(getattr(upload, name, None))


def _uploaded_cadastro_model(upload: Any) -> pd.DataFrame | None:
    """Retorna somente modelo classificado como cadastro.

    Não usa `model_df` como fallback para evitar que um modelo de estoque anexado
    por engano vire contrato de cadastro.
    """
    return _upload_attr(upload, 'cadastro_model_df')


def _uploaded_estoque_model(upload: Any) -> pd.DataFrame | None:
    """Retorna somente modelo classificado como estoque.

    Não usa `model_df` como fallback para evitar que um modelo de cadastro anexado
    por engano vire contrato de estoque.
    """
    return _upload_attr(upload, 'estoque_model_df')


def choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    """Modelo do cadastro: anexo correto > modelo salvo/Home > padrão interno."""
    uploaded = _uploaded_cadastro_model(upload)
    if isinstance(uploaded, pd.DataFrame):
        return uploaded
    home_model = get_home_cadastro_model()
    return home_model if isinstance(home_model, pd.DataFrame) else None


def choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    """Modelo do estoque: anexo correto > modelo salvo/Home > padrão interno."""
    uploaded = _uploaded_estoque_model(upload)
    if isinstance(uploaded, pd.DataFrame):
        return uploaded
    home_model = get_home_estoque_model()
    return home_model if isinstance(home_model, pd.DataFrame) else None


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

    Regra global:
    - cadastro por site usa apenas modelo de cadastro;
    - estoque por site usa apenas modelo de estoque;
    - anexo correto do usuário tem prioridade sobre padrão interno;
    - arquivo anexado da operação errada é ignorado neste fluxo;
    - na ausência de anexo correto, o padrão interno oficial vira o contrato;
    - a ordem das colunas do contrato é preservada no preview/download.
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
        st.success(f'Modelo de {operation_key} disponível para uso.')
        st.caption('Se você anexar um modelo correto nesta tela, ele terá prioridade. Se não anexar, o sistema usa o modelo interno oficial para esta operação.')

    caption = (
        'Opcional: anexe o modelo oficial de estoque do Bling. Se anexar modelo de cadastro por engano, ele será ignorado neste fluxo. Sem anexo correto, será usado o modelo interno oficial de estoque.'
        if operation_key == 'estoque'
        else 'Opcional: anexe o modelo oficial de cadastro do Bling. Se anexar modelo de estoque por engano, ele será ignorado neste fluxo. Sem anexo correto, será usado o modelo interno oficial de cadastro.'
    )

    return render_model_upload_box(
        title='Modelo do Bling para esta operação',
        operation=operation_key,
        key=f'model_upload_site_{operation_key}',
        required_model=False,
        caption=caption,
    )