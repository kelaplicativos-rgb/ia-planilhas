from __future__ import annotations

from io import BytesIO

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload


def clean_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna('')
    out.columns = [clean_text(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].map(clean_text)
    return out.fillna('')


def to_csv_bytes(df: pd.DataFrame, sep: str = ';') -> bytes:
    out = normalize_dataframe(df)
    buffer = BytesIO()
    out.to_csv(buffer, sep=sep, index=False, encoding='utf-8-sig')
    return buffer.getvalue()


def run_export_clean(payload: TablePayload) -> ModuleResult:
    out = normalize_dataframe(payload.df)
    return ModuleResult(
        ok=True,
        payload=payload.with_df(out, stage='export'),
        message='Exportacao V2 limpa aplicada.',
        metrics={'rows': len(out), 'columns': len(out.columns)},
    )


EXPORT_CLEAN_SPEC = ModuleSpec(
    key='v2_export_clean',
    title='Exportacao V2 limpa',
    description='Limpa textos e estrutura da tabela sem depender do exportador legado.',
    operation='global',
    stage='export',
    version='2.0.0',
    provides=('clean_table',),
    runner=run_export_clean,
)

__all__ = ['EXPORT_CLEAN_SPEC', 'clean_text', 'normalize_dataframe', 'run_export_clean', 'to_csv_bytes']
