from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.cadastro_engine import default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model

STALE_CADASTRO_DEFAULT_COLUMNS = [
    'Código',
    'Descrição',
    'Descrição Curta',
    'Descrição Complementar',
    'Unidade',
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
    'Preço de custo',
    'GTIN/EAN',
    'Marca',
    'Categoria',
    'NCM',
    'Origem',
    'Situação',
    'Formato',
    'Tipo',
    'Peso líquido',
    'Peso bruto',
    'Largura',
    'Altura',
    'Profundidade',
    'Estoque mínimo',
    'Estoque máximo',
    'URL Imagens',
    'Imagens',
    'Fornecedor',
    'Código do fornecedor',
    'Observações',
]

STALE_ESTOQUE_DEFAULT_COLUMNS = [
    'ID Produto',
    'Código',
    'Descrição',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
    'Observações',
]


def _columns(df: pd.DataFrame | None) -> list[str]:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return [str(column) for column in df.columns]
    return []


def _same_columns(left: list[str], right: list[str]) -> bool:
    return [str(value) for value in left] == [str(value) for value in right]


def _looks_like_cadastro_model(columns: list[str]) -> bool:
    normalized = {value.strip().lower() for value in columns}
    return 'ncm' in normalized or 'categoria do produto' in normalized or 'url imagens externas' in normalized


def cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    columns = _columns(df_modelo)
    if columns and not _same_columns(columns, STALE_CADASTRO_DEFAULT_COLUMNS):
        return df_modelo.copy().fillna('')
    return default_model()


def estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    columns = _columns(df_modelo)
    if not columns:
        return estoque_default_model()
    if _same_columns(columns, STALE_ESTOQUE_DEFAULT_COLUMNS):
        return estoque_default_model()
    if _looks_like_cadastro_model(columns):
        return estoque_default_model()
    return df_modelo.copy().fillna('')


def source_columns_from_df(df_source: pd.DataFrame) -> list[str]:
    return [str(column) for column in df_source.columns]


def target_columns_from_model(model: pd.DataFrame) -> list[str]:
    return [str(column) for column in model.columns]


__all__ = [
    'cadastro_model',
    'estoque_model',
    'source_columns_from_df',
    'target_columns_from_model',
]
