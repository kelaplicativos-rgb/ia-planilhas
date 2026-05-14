from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_csv_exporter import (
    INTERNAL_COLUMN_PREFIXES,
    clean_text,
    drop_internal_columns,
    final_csv_bytes,
    normalize_dataframe,
    sanitize_final_dataframe,
)
from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload

INTERNAL_COLUMN_PREFIX = INTERNAL_COLUMN_PREFIXES[0]


def to_csv_bytes(df: pd.DataFrame, sep: str = ';') -> bytes:
    return final_csv_bytes(
        df,
        operation='precos_multiloja',
        sep=sep,
        run_download_features=True,
    )


def run_export_clean(payload: TablePayload) -> ModuleResult:
    out = sanitize_final_dataframe(
        payload.df,
        operation=payload.operation or 'precos_multiloja',
        run_download_features=True,
    )
    return ModuleResult(
        ok=True,
        payload=payload.with_df(out, stage='export'),
        message='Exportação final compartilhada com features aplicada.',
        metrics={'rows': len(out), 'columns': len(out.columns)},
    )


EXPORT_CLEAN_SPEC = ModuleSpec(
    key='v2_export_clean',
    title='Exportação V2 limpa',
    description='Usa o exportador final compartilhado com features finais para limpar textos, remover colunas internas e gerar CSV padrão Bling.',
    operation='global',
    stage='export',
    version='2.2.0',
    provides=('clean_table',),
    runner=run_export_clean,
)

__all__ = [
    'EXPORT_CLEAN_SPEC',
    'INTERNAL_COLUMN_PREFIX',
    'clean_text',
    'drop_internal_columns',
    'normalize_dataframe',
    'run_export_clean',
    'to_csv_bytes',
]
