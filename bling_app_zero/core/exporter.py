from __future__ import annotations

from typing import Sequence

import pandas as pd

from bling_app_zero.core.final_csv_exporter import (
    build_final_csv_export,
    enforce_contract,
    filename_for_operation,
    final_csv_bytes,
    sanitize_final_dataframe,
)


def normalize_image_urls(value):
    return value


def enforce_export_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    return enforce_contract(df, contract_columns)


def sanitize_for_bling(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
) -> pd.DataFrame:
    # Nome legado mantido, mas agora é sanitização universal mínima.
    return sanitize_final_dataframe(
        df,
        operation='universal',
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=False,
    )


def to_bling_csv_bytes(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
) -> bytes:
    # Nome legado mantido por compatibilidade. Não aplica mais transformações Bling.
    return final_csv_bytes(
        df,
        operation='universal',
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=False,
    )


__all__ = [
    'build_final_csv_export',
    'enforce_export_contract',
    'filename_for_operation',
    'normalize_image_urls',
    'sanitize_for_bling',
    'to_bling_csv_bytes',
]
