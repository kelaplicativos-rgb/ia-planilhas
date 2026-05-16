from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_client import call_openai_json
from bling_app_zero.ai.ai_config import ai_is_enabled, get_ai_settings
from bling_app_zero.ai.ai_dataframe_tools import dataframe_snapshot
from bling_app_zero.ai.ai_mapping_suggester import suggest_mapping
from bling_app_zero.ai.ai_schema import AIResult

MIN_OPENAI_CONFIDENCE = 0.55

MAPPING_INSTRUCTIONS = """
Você é o motor de mapeamento do Mapeia.AI.
Sua tarefa é comparar colunas de origem com colunas do modelo de destino.
Use nomes de cabeçalhos, amostras de conteúdo e contexto de produto/estoque.
Não invente coluna de origem. Só use source_column que exista exatamente na lista de colunas da origem.
Não invente campo de destino. Só use target_column que exista exatamente na lista de colunas do modelo.
Quando não houver correspondência confiável, deixe source_column vazio.
Responda no formato:
{
  "suggestions": [
    {
      "target_column": "nome exato da coluna do modelo",
      "source_column": "nome exato da coluna de origem ou vazio",
      "confidence": 0.0,
      "reason": "motivo curto"
    }
  ]
}
""".strip()


def _target_snapshot(target_df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(target_df, pd.DataFrame):
        return {'columns': []}
    return {'columns': [str(column) for column in target_df.columns]}


def _sanitize_suggestions(raw: list[Any], source_columns: list[str], target_columns: list[str]) -> list[dict[str, Any]]:
    source_set = set(source_columns)
    target_set = set(target_columns)
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        target = str(item.get('target_column') or '').strip()
        source = str(item.get('source_column') or '').strip()
        if target not in target_set or target in seen:
            continue
        if source and source not in source_set:
            source = ''
        try:
            confidence = float(item.get('confidence') or 0)
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        if source and confidence < MIN_OPENAI_CONFIDENCE:
            source = ''
        clean.append(
            {
                'target_column': target,
                'source_column': source,
                'confidence': confidence,
                'reason': str(item.get('reason') or 'sugestão OpenAI validada'),
                'engine': 'openai',
            }
        )
        seen.add(target)
    return clean


def suggest_mapping_with_openai(source_df: pd.DataFrame, target_df: pd.DataFrame, *, operation: str = '') -> AIResult:
    local_result = suggest_mapping(source_df, target_df)
    if not ai_is_enabled():
        return local_result

    source_columns = [str(column) for column in source_df.columns] if isinstance(source_df, pd.DataFrame) else []
    target_columns = [str(column) for column in target_df.columns] if isinstance(target_df, pd.DataFrame) else []
    if not source_columns or not target_columns:
        return local_result

    settings = get_ai_settings()
    payload = {
        'operation': operation,
        'source': dataframe_snapshot(source_df, max_rows=8, max_columns=60),
        'target': _target_snapshot(target_df),
        'local_suggestions': local_result.data.get('suggestions', []) if isinstance(local_result.data, dict) else [],
    }
    openai_result = call_openai_json('mapping_suggester_openai', MAPPING_INSTRUCTIONS, payload, settings=settings)
    if not openai_result.ok:
        return AIResult(
            ok=True,
            task='mapping_suggester',
            message='OpenAI indisponível; usando sugestões locais.',
            data={**local_result.data, 'engine': 'local_fallback', 'openai_error': openai_result.error},
        )

    raw_suggestions = openai_result.data.get('suggestions', []) if isinstance(openai_result.data, dict) else []
    suggestions = _sanitize_suggestions(raw_suggestions, source_columns, target_columns)
    if not suggestions:
        return AIResult(
            ok=True,
            task='mapping_suggester',
            message='OpenAI não retornou sugestões válidas; usando sugestões locais.',
            data={**local_result.data, 'engine': 'local_fallback_empty_openai'},
        )

    mapping = {
        item['target_column']: item['source_column']
        for item in suggestions
        if item.get('target_column') and item.get('source_column') and float(item.get('confidence') or 0) >= 0.6
    }
    return AIResult(
        ok=True,
        task='mapping_suggester',
        message=f'{len(mapping)} campo(s) sugerido(s) pela OpenAI com validação local.',
        data={'mapping': mapping, 'suggestions': suggestions, 'engine': 'openai_validated'},
    )


__all__ = ['MIN_OPENAI_CONFIDENCE', 'suggest_mapping_with_openai']
