from __future__ import annotations

from io import BytesIO

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload

INTERNAL_COLUMN_PREFIX = '_v2_'


def clean_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def drop_internal_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    internal = [column for column in df.columns if str(column).startswith(INTERNAL_COLUMN_PREFIX)]
    return df.drop(columns=internal, errors='ignore') if internal else df


def normalize_dataframe(df: pd.DataFrame, *, keep_internal: bool = False) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna('')
    if not keep_internal:
        out = drop_internal_columns(out)
    out.columns = [clean_text(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].map(clean_text)
    return out.fillna('')


def to_csv_bytes(df: pd.DataFrame, sep: str = ';') -> bytes:
    out = normalize_dataframe(df, keep_internal=False)
    buffer = BytesIO()
    out.to_csv(buffer, sep=sep, index=False, encoding='utf-8-sig')
    return buffer.getvalue()


def run_export_clean(payload: TablePayload) -> ModuleResult:
    out = normalize_dataframe(payload.df, keep_internal=False)
    return ModuleResult(
        ok=True,
        payload=payload.with_df(out, stage='export'),
        message='Exportacao V2 limpa aplicada.',
        metrics={'rows': len(out), 'columns': len(out.columns)},
    )


EXPORT_CLEAN_SPEC = ModuleSpec(
    key='v2_export_clean',
    title='Exportacao V2 limpa',
    description='Limpa textos, remove colunas internas e gera estrutura final sem legado.',
    operation='global',
    stage='export',
    version='2.0.0',
    provides=('clean_table',),
    runner=run_export_clean,
)

__all__ = ['EXPORT_CLEAN_SPEC', 'INTERNAL_COLUMN_PREFIX', 'clean_text', 'drop_internal_columns', 'normalize_dataframe', 'run_export_clean', 'to_csv_bytes']
