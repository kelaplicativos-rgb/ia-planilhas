from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_column_reader import read_columns_locally
from bling_app_zero.ai.ai_content_checker import check_content_coherence
from bling_app_zero.ai.ai_mapping_suggester import suggest_mapping
from bling_app_zero.ai.ai_quality_score import score_dataframe_quality
from bling_app_zero.ai.ai_schema import AIResult


def analyze_origin(source_df: pd.DataFrame) -> AIResult:
    columns = read_columns_locally(source_df)
    coherence = check_content_coherence(source_df)
    quality = score_dataframe_quality(source_df)
    return AIResult(
        ok=True,
        task='analyze_origin',
        message='Análise local da origem concluída.',
        data={
            'columns': columns.data,
            'coherence': coherence.data,
            'quality': quality.data,
        },
    )


def analyze_mapping(source_df: pd.DataFrame, target_df: pd.DataFrame) -> AIResult:
    mapping = suggest_mapping(source_df, target_df)
    quality = score_dataframe_quality(source_df)
    return AIResult(
        ok=True,
        task='analyze_mapping',
        message='Sugestão local de mapeamento concluída.',
        data={
            'mapping': mapping.data,
            'quality': quality.data,
        },
    )


def run_ai_local_task(task: str, payload: dict[str, Any]) -> AIResult:
    source_df = payload.get('source_df')
    target_df = payload.get('target_df')
    if task == 'analyze_origin' and isinstance(source_df, pd.DataFrame):
        return analyze_origin(source_df)
    if task == 'analyze_mapping' and isinstance(source_df, pd.DataFrame) and isinstance(target_df, pd.DataFrame):
        return analyze_mapping(source_df, target_df)
    return AIResult(ok=False, task=task, message='Tarefa de IA local inválida ou sem DataFrame.', error='invalid_task_payload')


__all__ = ['analyze_mapping', 'analyze_origin', 'run_ai_local_task']
