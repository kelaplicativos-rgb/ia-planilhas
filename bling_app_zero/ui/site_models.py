from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_models import (
    HOME_CADASTRO_MODEL_SOURCE_KEY,
    HOME_ESTOQUE_MODEL_SOURCE_KEY,
    get_home_cadastro_model,
    get_home_estoque_model,
)
from bling_app_zero.ui.model_upload import render_model_upload_box

DEFAULT_SYSTEM_MODEL_SOURCE = 'padrao_sistema'


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


def _home_model_source(operation: str) -> str:
    normalized = str(operation or '').strip().lower()
    key = HOME_ESTOQUE_MODEL_SOURCE_KEY if normalized == 'estoque' else HOME_CADASTRO_MODEL_SOURCE_KEY
    return str(st.session_state.get(key) or '').strip()


def _home_model_is_system_default(operation: str) -> bool:
    return _home_model_source(operation) == DEFAULT_SYSTEM_MODEL_SOURCE


def _uploaded_cadastro_model(upload: Any) -> pd.DataFrame | None:
    return _upload_attr(upload, 'cadastro_model_df') or _upload_attr(upload, 'model_df')


def _uploaded_estoque_model(upload: Any) -> pd.DataFrame | None:
    return _upload_attr(upload, 'estoque_model_df') or _upload_attr(upload, 'model_df')


def choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    """Escolhe o modelo de cadastro respeitando upload recente acima do padrão interno."""
    uploaded = _uploaded_cadastro_model(upload)
    if isinstance(uploaded, pd.DataFrame):
        return uploaded

    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame) and not _home_model_is_system_default('cadastro'):
        return home_model

    return home_model if isinstance(home_model, pd.DataFrame) else None


def choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    """Escolhe o modelo de estoque sem deixar o padrão de 4 colunas atropelar o anexo.

    BLINGFIX:
    - modelo anexado neste painel tem prioridade máxima;
    - modelo anexado na Home é aceito;
    - modelo padrão interno de estoque não é tratado como modelo real para captura por site;
    - sem modelo real, o botão de busca continua bloqueado.
    """
    uploaded = _uploaded_estoque_model(upload)
    if isinstance(uploaded, pd.DataFrame):
        return uploaded

    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame) and not _home_model_is_system_default('estoque'):
        return home_model

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
    - estoque por site usa apenas modelo de estoque real;
    - nunca mistura cadastro + estoque na mesma captura;
    - estoque por site não usa fallback solto sem modelo;
    - a ordem das colunas é a ordem exata do modelo anexado.
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
        return isinstance(get_home_estoque_model(), pd.DataFrame) and not _home_model_is_system_default('estoque')
    return isinstance(get_home_cadastro_model(), pd.DataFrame) and not _home_model_is_system_default('cadastro')


def render_optional_site_model_upload(operation: str = 'cadastro') -> object:
    normalized = str(operation or '').strip().lower()
    operation_key = 'estoque' if normalized == 'estoque' else 'cadastro'

    if has_home_site_model_for_operation(operation_key):
        st.success(f'Modelo de {operation_key} anexado na Home e pronto para uso.')
        st.caption('Este fluxo vai usar exatamente as colunas desse modelo salvo.')
        return EmptyModelUpload()

    if operation_key == 'estoque' and _home_model_is_system_default('estoque'):
        st.warning('Existe um modelo padrão interno de estoque com poucas colunas, mas ele não será usado como modelo final. Anexe o modelo oficial do Bling para manter a estrutura completa.')
    elif get_home_cadastro_model() is not None or get_home_estoque_model() is not None:
        st.warning('Existe modelo carregado na Home, mas não para esta operação.')

    required_model = operation_key == 'estoque'
    caption = (
        'Obrigatório para estoque por site: anexe o modelo oficial do Bling. O CSV final manterá exatamente as colunas e a ordem desse modelo.'
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