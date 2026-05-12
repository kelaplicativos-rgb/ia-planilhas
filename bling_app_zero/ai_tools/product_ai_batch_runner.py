from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.ai_tools.product_ai_reviewer import ProductAISuggestion, generate_product_ai_suggestions

ProgressCallback = Callable[[dict[str, Any]], None]
DEFAULT_AI_BATCH_SIZE = 10


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


def _batched_df(df: pd.DataFrame, *, start_offset: int, max_rows: int, batch_size: int) -> list[pd.DataFrame]:
    start = max(0, int(start_offset or 0))
    end = min(len(df), start + max(0, int(max_rows or 0)))
    limited = df.iloc[start:end]
    return [limited.iloc[pos : pos + batch_size] for pos in range(0, len(limited), batch_size)]


def generate_product_ai_suggestions_batched(
    df: pd.DataFrame,
    *,
    actions: dict[str, bool] | None = None,
    max_rows: int | None = None,
    custom_task: str = '',
    batch_size: int = DEFAULT_AI_BATCH_SIZE,
    start_offset: int = 0,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[ProductAISuggestion], str, int]:
    """Executa a IA do preview em lotes com progresso e retomada.

    Retorna: sugestões, status e próximo offset processável.
    O offset permite continuar de onde parou em uma próxima execução.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 'Sem dados finais para revisar.', 0

    total_rows = len(df)
    start = max(0, min(int(start_offset or 0), total_rows))
    remaining = max(0, total_rows - start)
    rows_to_process = min(remaining, int(max_rows or remaining))
    selected_batch_size = max(1, int(batch_size or DEFAULT_AI_BATCH_SIZE))

    if rows_to_process <= 0:
        _emit_progress(progress_callback, current=total_rows, total=total_rows, stage='Concluído', message='Todos os produtos já foram analisados.')
        return [], 'Todos os produtos já foram analisados.', total_rows

    suggestions_all: list[ProductAISuggestion] = []
    status_parts: list[str] = []
    processed = start

    _emit_progress(
        progress_callback,
        current=start,
        total=total_rows,
        stage='Preparando',
        message=f'Preparando IA para analisar {rows_to_process} produto(s), a partir da linha {start + 1}.',
    )

    for batch_number, batch in enumerate(_batched_df(df, start_offset=start, max_rows=rows_to_process, batch_size=selected_batch_size), start=1):
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

    final_stage = 'Concluído' if processed >= total_rows else 'Pausado'
    final_message = (
        f'IA concluiu {processed}/{total_rows} produto(s).'
        if processed >= total_rows
        else f'Rodada concluída em {processed}/{total_rows}. Continue para analisar o restante.'
    )
    _emit_progress(progress_callback, current=processed, total=total_rows, stage=final_stage, message=final_message)

    if suggestions_all:
        status = 'Sugestões geradas em lotes. ' + ' | '.join(status_parts[:3])
        if processed < total_rows:
            status += f' Próxima execução continua em {processed + 1}/{total_rows}.'
        return suggestions_all, status, processed
    status = status_parts[0] if status_parts else 'A IA não encontrou alterações seguras para sugerir nesta rodada.'
    if processed < total_rows:
        status += f' Próxima execução continua em {processed + 1}/{total_rows}.'
    return [], status, processed


__all__ = ['DEFAULT_AI_BATCH_SIZE', 'generate_product_ai_suggestions_batched']
