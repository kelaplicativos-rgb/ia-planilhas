from __future__ import annotations

import pandas as pd

PREVIEW_CELL_MAX_CHARS = 72


def truncate_preview_cell(value: object, max_chars: int = PREVIEW_CELL_MAX_CHARS) -> object:
    """Encurta apenas a exibicao da previa, sem alterar o DataFrame real/exportado."""
    if pd.isna(value):
        return ''
    text = str(value).replace('\r', ' ').replace('\n', ' ').strip()
    if len(text) <= max_chars:
        return text
    return f'{text[:max_chars].rstrip()}...'


def build_preview_display_df(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    preview = df.head(max_rows).copy()
    if preview.empty:
        return preview
    for column in preview.columns:
        preview[column] = preview[column].map(truncate_preview_cell)
    return preview
