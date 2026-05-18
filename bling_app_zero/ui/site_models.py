from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model


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
    """Retorna modelo classificado como cadastro/marketplace."""
    cadastro = _upload_attr(upload, 'cadastro_model_df')
    if isinstance(cadastro, pd.DataFrame):
        return cadastro
    estoque = _upload_attr(upload, 'estoque_model_df')
    generic = _upload_attr(upload, 'model_df')
    if isinstance(generic, pd.DataFrame) and not isinstance(estoque, pd.DataFrame):
        return generic
    return None


def _uploaded_estoque_model(upload: Any) -> pd.DataFrame | None:
    """Retorna somente modelo classificado como estoque."""
    return _upload_attr(upload, 'estoque_model_df')


def choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    """Modelo do cadastro/marketplace salvo na etapa Modelo."""
    uploaded = _uploaded_cadastro_model(upload)
    if isinstance(uploaded, pd.DataFrame):
        return uploaded
    home_model = get_home_cadastro_model()
    return home_model if isinstance(home_model, pd.DataFrame) else None


def choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    """Modelo do estoque salvo na etapa Modelo."""
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
    """Retorna somente as colunas do modelo da operação atual."""
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


def _home_model_summary(operation_key: str) -> str:
    df = get_home_estoque_model() if operation_key == 'estoque' else get_home_cadastro_model()
    if isinstance(df, pd.DataFrame):
        return f'Modelo já definido na etapa Modelo: {len(df.columns)} coluna(s).'
    return 'Nenhum modelo desta operação foi encontrado na etapa Modelo.'


def render_optional_site_model_upload(operation: str = 'cadastro') -> object:
    """Mantém a busca por site sem upload duplicado de modelo.

    O modelo de destino deve ser anexado uma única vez na etapa Modelo de
    destino. Esta etapa apenas lê o modelo já salvo para definir quais campos
    serão buscados no site. Isso evita confundir o usuário com dois pontos de
    anexo para o mesmo arquivo.
    """
    normalized = str(operation or '').strip().lower()
    operation_key = 'estoque' if normalized == 'estoque' else 'cadastro'

    if has_home_site_model_for_operation(operation_key):
        st.success(_home_model_summary(operation_key))
        st.caption('A busca por site usará o modelo já anexado no início. Não é necessário anexar a mesma planilha novamente.')
    else:
        st.warning('Modelo de destino não encontrado nesta sessão. Volte na etapa Modelo de destino e anexe o modelo correto uma única vez.')

    return EmptyModelUpload()


__all__ = [
    'EmptyModelUpload',
    'choose_site_cadastro_model_df',
    'choose_site_estoque_model_df',
    'choose_site_model_df',
    'columns_from_df',
    'has_home_site_model_for_operation',
    'render_optional_site_model_upload',
    'requested_columns_for_site_capture',
    'unique_columns',
]
