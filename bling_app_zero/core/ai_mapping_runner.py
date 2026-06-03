from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.ai_mapping_assistant import apply_ai_mapping_assist
from bling_app_zero.core.ai_mapping_availability import ai_mapping_availability

RESPONSIBLE_FILE = 'bling_app_zero/core/ai_mapping_runner.py'


@dataclass(frozen=True)
class AIMappingRunResult:
    enabled: bool
    applied: int
    suggestions: dict[str, str]
    reason: str = ''
    status: str = 'inactive'


def run_ai_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    *,
    only_uncertain: bool = False,
) -> AIMappingRunResult:
    availability = ai_mapping_availability()
    if not availability.enabled:
        return AIMappingRunResult(False, 0, {}, availability.reason or 'OPENAI_API_KEY ausente', 'inactive')
    if availability.remaining_calls <= 0:
        return AIMappingRunResult(True, 0, {}, availability.reason or 'limite de IA da sessão atingido', 'limit')

    result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=only_uncertain)
    if not getattr(result, 'enabled', False):
        return AIMappingRunResult(False, 0, {}, str(getattr(result, 'reason', '') or 'IA indisponível'), 'inactive')
    applied = int(getattr(result, 'applied', 0) or 0)
    suggestions = dict(getattr(result, 'suggestions', {}) or {})
    if applied <= 0:
        return AIMappingRunResult(True, 0, suggestions, str(getattr(result, 'reason', '') or 'sem alterações seguras'), 'no_safe_changes')
    return AIMappingRunResult(True, applied, suggestions, str(getattr(result, 'reason', '') or 'ok'), f'applied:{applied}')


def merge_ai_run_suggestions(current_mapping: dict[str, str], run_result: AIMappingRunResult) -> dict[str, str]:
    merged = dict(current_mapping or {})
    for target, source in dict(run_result.suggestions or {}).items():
        merged[str(target)] = str(source or '')
    return merged


__all__ = [
    'AIMappingRunResult',
    'RESPONSIBLE_FILE',
    'merge_ai_run_suggestions',
    'run_ai_mapping',
]
