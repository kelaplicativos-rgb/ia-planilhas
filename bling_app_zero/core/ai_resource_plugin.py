from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from bling_app_zero.ai_tools.product_ai_batch_runner import DEFAULT_AI_BATCH_SIZE, generate_product_ai_suggestions_batched
from bling_app_zero.ai_tools.product_ai_reviewer import (
    ai_ready,
    apply_product_ai_suggestions,
    detect_product_columns,
    suggestions_to_dataframe,
)
from bling_app_zero.core.marketplace_text_guard import alerts_to_dataframe, analyze_marketplace_text
from bling_app_zero.core.text import clean_cell

AI_RESOURCE_DEFAULT_ACTIONS = {
    'title': True,
    'description': True,
    'grammar': False,
    'ncm': True,
    'code': False,
    'clean': False,
}

AI_RESOURCE_EXAMPLE_TASKS = [
    'Crie títulos para produtos que estão sem nome.',
    'Padronize os títulos com marca + modelo quando essas informações existirem.',
    'Melhore as descrições complementares vazias ou muito curtas.',
    'Sugira NCM para produtos que estão com NCM vazio.',
    'Limpe textos quebrados, espaços duplicados e caracteres estranhos em colunas editáveis.',
    'Crie códigos internos somente quando existir uma coluna própria para isso e ela estiver vazia.',
]

DESCRIPTION_LIMITS = {
    'pequena': 220,
    'media': 520,
    'grande': 1000,
}

DEFAULT_AI_RESOURCE_POLICY = {
    'limit_title_60': True,
    'description_size': 'media',
    'marketplace_text_guard': False,
    'out_of_context_filter': False,
    'blocked_terms': '',
    'context_filter_terms': '',
}


@dataclass(frozen=True)
class AIResourceRequest:
    operation: str = 'arquivo'
    actions: dict[str, bool] | None = None
    custom_task: str = ''
    batch_size: int = DEFAULT_AI_BATCH_SIZE
    max_rows: int | None = None
    start_offset: int = 0
    policy: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIResourceResult:
    suggestions_df: pd.DataFrame
    status: str
    next_offset: int
    applied: bool = False
    df_applied: pd.DataFrame | None = None


def normalize_ai_actions(actions: dict[str, Any] | None) -> dict[str, bool]:
    output = dict(AI_RESOURCE_DEFAULT_ACTIONS)
    if isinstance(actions, dict):
        for key, value in actions.items():
            output[str(key)] = bool(value)
    return output


def normalize_ai_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    output = dict(DEFAULT_AI_RESOURCE_POLICY)
    if isinstance(policy, dict):
        output.update(policy)
    if str(output.get('description_size') or 'media') not in DESCRIPTION_LIMITS:
        output['description_size'] = 'media'
    return output


def _truncate_text(value: object, limit: int) -> str:
    text = clean_cell(value)
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut


def apply_ai_resource_policy_to_dataframe(suggestions_df: pd.DataFrame, policy: dict[str, Any] | None = None) -> pd.DataFrame:
    if not isinstance(suggestions_df, pd.DataFrame) or suggestions_df.empty:
        return suggestions_df

    normalized_policy = normalize_ai_policy(policy)
    limit_title = bool(normalized_policy['limit_title_60'])
    description_size = str(normalized_policy['description_size'])
    description_limit = DESCRIPTION_LIMITS.get(description_size, DESCRIPTION_LIMITS['media'])

    out = suggestions_df.copy()
    if out.empty or 'Sugestão IA' not in out.columns or 'Campo' not in out.columns:
        return out

    def _adjust(row: pd.Series) -> str:
        field = str(row.get('Campo') or '').strip().lower()
        suggestion = clean_cell(row.get('Sugestão IA', ''))
        if field == 'title' and limit_title:
            return _truncate_text(suggestion, 60)
        if field == 'description':
            return _truncate_text(suggestion, description_limit)
        return suggestion

    out['Sugestão IA'] = out.apply(_adjust, axis=1)
    return out.reset_index(drop=True)


def run_ai_resource_plugin(
    df: pd.DataFrame,
    request: AIResourceRequest,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AIResourceResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return AIResourceResult(pd.DataFrame(), 'Sem dados para revisar.', 0)

    actions = normalize_ai_actions(request.actions)
    suggestions, status, next_offset = generate_product_ai_suggestions_batched(
        df,
        actions={
            'title': bool(actions.get('title')),
            'description': bool(actions.get('description')),
            'grammar': bool(actions.get('grammar')),
            'ncm': bool(actions.get('ncm')),
        },
        max_rows=int(request.max_rows or len(df)),
        custom_task=str(request.custom_task or '').strip(),
        batch_size=int(request.batch_size or DEFAULT_AI_BATCH_SIZE),
        start_offset=int(request.start_offset or 0),
        progress_callback=progress_callback,
    )
    suggestions_df = suggestions_to_dataframe(suggestions)
    suggestions_df = apply_ai_resource_policy_to_dataframe(suggestions_df, request.policy)
    return AIResourceResult(suggestions_df, status, int(next_offset or 0))


def apply_ai_resource_suggestions(df: pd.DataFrame, edited_suggestions: pd.DataFrame) -> AIResourceResult:
    if not isinstance(df, pd.DataFrame):
        return AIResourceResult(pd.DataFrame(), 'Origem inválida.', 0, applied=False)
    df_applied = apply_product_ai_suggestions(df, edited_suggestions)
    return AIResourceResult(pd.DataFrame(), 'Sugestões aplicadas.', len(df_applied), applied=True, df_applied=df_applied)


def ai_resource_columns(df: pd.DataFrame) -> dict[str, str]:
    if not isinstance(df, pd.DataFrame):
        return {}
    return detect_product_columns(df)


def ai_resource_ready() -> bool:
    return ai_ready()


def analyze_ai_resource_guard(df: pd.DataFrame, policy: dict[str, Any] | None = None) -> pd.DataFrame:
    normalized_policy = normalize_ai_policy(policy)
    alerts = analyze_marketplace_text(df, normalized_policy)
    return alerts_to_dataframe(alerts)


__all__ = [
    'AI_RESOURCE_DEFAULT_ACTIONS',
    'AI_RESOURCE_EXAMPLE_TASKS',
    'DEFAULT_AI_RESOURCE_POLICY',
    'AIResourceRequest',
    'AIResourceResult',
    'ai_resource_columns',
    'ai_resource_ready',
    'analyze_ai_resource_guard',
    'apply_ai_resource_policy_to_dataframe',
    'apply_ai_resource_suggestions',
    'normalize_ai_actions',
    'normalize_ai_policy',
    'run_ai_resource_plugin',
]
