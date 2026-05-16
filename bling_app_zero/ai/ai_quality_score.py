from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_content_checker import check_content_coherence
from bling_app_zero.ai.ai_schema import AIResult

REQUIRED_HINTS = ('descricao', 'nome', 'produto', 'titulo', 'preco', 'valor')


def _non_empty_ratio(df: pd.DataFrame) -> float:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 0.0
    total = max(1, len(df) * len(df.columns))
    filled = int(df.fillna('').astype(str).applymap(lambda value: bool(str(value).strip())).sum().sum())
    return filled / total


def _has_required_hint(columns: list[str], hint_group: tuple[str, ...]) -> bool:
    normalized = ' | '.join(column.lower() for column in columns)
    return any(hint in normalized for hint in hint_group)


def score_dataframe_quality(df: pd.DataFrame) -> AIResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return AIResult(ok=True, task='quality_score', message='Planilha vazia.', data={'score': 0, 'issues': ['Planilha vazia.']})

    columns = [str(column) for column in df.columns]
    issues: list[str] = []
    score = 100

    ratio = _non_empty_ratio(df)
    if ratio < 0.3:
        score -= 25
        issues.append('Muitos campos vazios na origem.')
    elif ratio < 0.6:
        score -= 10
        issues.append('Alguns campos importantes podem estar vazios.')

    if not _has_required_hint(columns, ('descricao', 'descrição', 'nome', 'produto', 'titulo', 'título')):
        score -= 20
        issues.append('Não encontrei coluna clara de nome/descrição do produto.')
    if not _has_required_hint(columns, ('preco', 'preço', 'valor', 'price')):
        score -= 15
        issues.append('Não encontrei coluna clara de preço/valor.')

    coherence = check_content_coherence(df)
    coherence_issues = coherence.data.get('issues', []) if isinstance(coherence.data, dict) else []
    if coherence_issues:
        score -= min(25, len(coherence_issues) * 5)
        for item in coherence_issues[:5]:
            if isinstance(item, dict):
                issues.append(str(item.get('message') or 'Possível incoerência entre cabeçalho e conteúdo.'))

    score = max(0, min(100, score))
    return AIResult(
        ok=True,
        task='quality_score',
        message=f'Nota de qualidade: {score}/100.',
        data={'score': score, 'issues': issues, 'filled_ratio': round(ratio, 3), 'coherence': coherence.data},
    )


__all__ = ['score_dataframe_quality']
