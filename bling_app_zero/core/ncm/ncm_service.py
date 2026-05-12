from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.ncm.ncm_engine import suggest_ncm_for_product
from bling_app_zero.core.text import normalize_key

NCM_OUTPUT_COLUMN = 'NCM sugerido pela IA'
NCM_CONFIDENCE_COLUMN = 'Confiança NCM'
NCM_REASON_COLUMN = 'Observação NCM'
NCM_SOURCE_COLUMN = 'Fonte NCM'


def _find_ncm_column(df: pd.DataFrame) -> str:
    for column in df.columns:
        key = normalize_key(column)
        if key == 'ncm' or key.endswith(' ncm') or 'codigo ncm' in key:
            return str(column)
    return ''


def _empty_ncm(value: Any) -> bool:
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return len(digits) != 8


def apply_ncm_suggestions(
    df: pd.DataFrame,
    *,
    use_ai: bool = True,
    apply_high_confidence: bool = True,
    limit: int = 300,
) -> pd.DataFrame:
    """Sugere NCM para linhas sem NCM.

    Alta confiança pode preencher a coluna NCM quando apply_high_confidence=True.
    As demais sugestões ficam em colunas auxiliares para revisão humana.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy().fillna('')
    ncm_column = _find_ncm_column(out)
    if not ncm_column:
        out['NCM'] = ''
        ncm_column = 'NCM'

    for column in [NCM_OUTPUT_COLUMN, NCM_CONFIDENCE_COLUMN, NCM_REASON_COLUMN, NCM_SOURCE_COLUMN]:
        if column not in out.columns:
            out[column] = ''

    processed = 0
    for row_index, row in out.iterrows():
        if processed >= limit:
            break
        if not _empty_ncm(out.at[row_index, ncm_column]):
            continue
        suggestion = suggest_ncm_for_product(row.to_dict(), use_ai=use_ai)
        processed += 1
        if not suggestion.ncm:
            out.at[row_index, NCM_CONFIDENCE_COLUMN] = suggestion.confidence
            out.at[row_index, NCM_REASON_COLUMN] = suggestion.reason
            out.at[row_index, NCM_SOURCE_COLUMN] = suggestion.source
            continue
        out.at[row_index, NCM_OUTPUT_COLUMN] = suggestion.ncm
        out.at[row_index, NCM_CONFIDENCE_COLUMN] = suggestion.confidence
        out.at[row_index, NCM_REASON_COLUMN] = suggestion.reason
        out.at[row_index, NCM_SOURCE_COLUMN] = suggestion.source
        if apply_high_confidence and suggestion.should_apply:
            out.at[row_index, ncm_column] = suggestion.ncm

    return out


__all__ = [
    'NCM_CONFIDENCE_COLUMN',
    'NCM_OUTPUT_COLUMN',
    'NCM_REASON_COLUMN',
    'NCM_SOURCE_COLUMN',
    'apply_ncm_suggestions',
]
