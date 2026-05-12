from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.ai_tools.product_ai_reviewer import ProductAISuggestion, generate_product_ai_suggestions

ProgressCallback = Callable[[dict[str, Any]], None]
DEFAULT_AI_BATCH_SIZE = 20


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    current: int,
    total: int,
    stage: str,
    message: str,
) -> None:
    if not callback:
        return
    total_safe = max(1, int(total or 1))
    current_safe = max(0, min(int(current or 0), total_safe))
    callback(
        {
            'current': current_safe,
            'total': total_safe,
            'progress': current_safe / total_safe,
            'percent': int((current_safe / total_safe) * 100),
            'stage': stage,
            'message': message,
        }
    )


def _batched_df(df: pd.DataFrame, max_rows: int, batch_size: int) -> list[pd.DataFrame]:
    limited = df.head(max_rows)
    return [limited.iloc[start : start + batch_size] for start in range(0, len(limited), batch_size)]


def generate_product_ai_suggestions_batched(
    df: pd.DataFrame,
    *,
    actions: dict[str, bool] | None = None,
    max_rows: int | None = None,
    custom_task: str = '',
    batch_size: int = DEFAULT_AI_BATCH_SIZE,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[ProductAISuggestion], str]:
    """Executa a IA do preview em lotes para alimentar barra de progresso.

    Mantém o motor original intacto e só divide a execução em partes menores.
    Assim a tela consegue mostrar quantos produtos já foram processados.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 'Sem dados finais para revisar.'

    total_rows = min(len(df), int(max_rows or len(df)))
    selected_batch_size = max(1, int(batch_size or DEFAULT_AI_BATCH_SIZE))
    suggestions_all: list[ProductAISuggestion] = []
    status_parts: list[str] = []
    processed = 0

    _emit_progress(
        progress_callback,
        current=0,
        total=total_rows,
        stage='Preparando',
        message=f'Preparando IA para {total_rows} produto(s)...',
    )

    for batch_number, batch in enumerate(_batched_df(df, total_rows, selected_batch_size), start=1):
        batch_len = len(batch)
        start_item = processed + 1
        end_item = processed + batch_len
        _emit_progress(
            progress_callback,
            current=processed,
            total=total_rows,
            stage='Analisando',
            message=f'Analisando produtos {start_item} a {end_item} de {total_rows}...',
        )

        suggestions, status = generate_product_ai_suggestions(
            batch,
            actions=actions,
            max_rows=batch_len,
            custom_task=custom_task,
        )
        suggestions_all.extend(suggestions)
        if status and status not in status_parts:
            status_parts.append(status)

        processed += batch_len
        _emit_progress(
            progress_callback,
            current=processed,
            total=total_rows,
            stage='Processando',
            message=f'{processed}/{total_rows} produto(s) revisado(s). Lote {batch_number} concluído.',
        )

    _emit_progress(
        progress_callback,
        current=total_rows,
        total=total_rows,
        stage='Concluído',
        message=f'IA concluiu {total_rows}/{total_rows} produto(s).',
    )

    if suggestions_all:
        return suggestions_all, 'Sugestões geradas em lotes. ' + ' | '.join(status_parts[:3])
    return [], status_parts[0] if status_parts else 'A IA não encontrou alterações seguras para sugerir.'


__all__ = ['DEFAULT_AI_BATCH_SIZE', 'generate_product_ai_suggestions_batched']
