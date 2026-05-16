from __future__ import annotations

import pandas as pd

from bling_app_zero.ai.ai_header_matcher import suggest_header_matches
from bling_app_zero.ai.ai_schema import AIResult


def suggest_mapping(source_df: pd.DataFrame, target_df: pd.DataFrame) -> AIResult:
    result = suggest_header_matches(source_df, target_df)
    suggestions = result.data.get('suggestions', []) if isinstance(result.data, dict) else []
    mapping = {
        item.get('target_column', ''): item.get('source_column', '')
        for item in suggestions
        if item.get('target_column') and item.get('source_column') and float(item.get('confidence') or 0) >= 0.6
    }
    return AIResult(
        ok=True,
        task='mapping_suggester',
        message=f'{len(mapping)} campo(s) sugerido(s) com confiança mínima.',
        data={'mapping': mapping, 'suggestions': suggestions},
    )


__all__ = ['suggest_mapping']
