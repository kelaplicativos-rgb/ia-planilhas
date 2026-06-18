from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_models import cadastro_default_model, enforce_model_contract
from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping, auto_map_columns

DEFAULT_CADASTRO_COLUMNS = list(cadastro_default_model().columns)


def default_model() -> pd.DataFrame:
    return cadastro_default_model()


def _first_source_column_by_kind(df_source: pd.DataFrame, kind: str) -> str:
    if not isinstance(df_source, pd.DataFrame):
        return ''
    for column in df_source.columns:
        if infer_kind(str(column)) == kind:
            return str(column)
    return ''


def _fill_missing_image_columns(final: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    out = final.copy().fillna('') if isinstance(final, pd.DataFrame) else pd.DataFrame()
    image_source = _first_source_column_by_kind(source, 'imagem')
    if not image_source:
        return out
    for column in out.columns:
        if infer_kind(str(column)) != 'imagem':
            continue
        try:
            has_value = out[column].astype(str).str.strip().ne('').any()
        except Exception:
            has_value = False
        if not has_value and image_source in source.columns:
            out[column] = source[image_source].fillna('').astype(str)
    return out.fillna('')


def run_cadastro_engine(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    model = df_model.copy().fillna('') if isinstance(df_model, pd.DataFrame) and len(df_model.columns) else default_model()
    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    mapping = auto_map_columns(source, model)
    final = apply_mapping(source, model, mapping)
    final = _fill_missing_image_columns(final, source)
    final = enforce_model_contract(final, 'cadastro', model)
    return sanitize_for_bling(final, operation='cadastro'), mapping
