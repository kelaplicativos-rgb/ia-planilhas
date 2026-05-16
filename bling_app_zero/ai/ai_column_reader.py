from __future__ import annotations

import pandas as pd

from bling_app_zero.ai.ai_dataframe_tools import profile_dataframe_columns
from bling_app_zero.ai.ai_schema import AIResult


def read_columns_locally(df: pd.DataFrame) -> AIResult:
    profiles = profile_dataframe_columns(df)
    return AIResult(
        ok=True,
        task='column_reader',
        message=f'{len(profiles)} coluna(s) analisada(s).',
        data={'profiles': profiles},
    )


__all__ = ['read_columns_locally']
