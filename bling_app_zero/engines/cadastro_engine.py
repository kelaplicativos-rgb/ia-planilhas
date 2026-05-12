from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping, auto_map_columns

DEFAULT_CADASTRO_COLUMNS = [
    'Código',
    'Descrição',
    'Descrição Curta',
    'Preço de venda',
    'GTIN/EAN',
    'Marca',
    'Categoria',
    'URL Imagens',
    'NCM',
]


def default_model() -> pd.DataFrame:
    return pd.DataFrame(columns=DEFAULT_CADASTRO_COLUMNS)


def run_cadastro_engine(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    model = df_model if isinstance(df_model, pd.DataFrame) and len(df_model.columns) else default_model()
    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    mapping = auto_map_columns(source, model)
    final = apply_mapping(source, model, mapping)
    return sanitize_for_bling(final, operation='cadastro'), mapping
