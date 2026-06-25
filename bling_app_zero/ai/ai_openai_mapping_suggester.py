from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_client import call_openai_json
from bling_app_zero.ai.ai_config import ai_is_enabled, get_ai_settings
from bling_app_zero.ai.ai_dataframe_tools import dataframe_snapshot
from bling_app_zero.ai.ai_mapping_suggester import suggest_mapping
from bling_app_zero.ai.ai_schema import AIResult
from bling_app_zero.core.mapping_certainty_guard import filter_mapping_to_certain, is_unique_certain_mapping

MIN_OPENAI_CONFIDENCE = 1.0

MAPPING_INSTRUCTIONS = """
Você é o motor de mapeamento do Mapeia.AI.
Sua tarefa é comparar colunas de origem com colunas do modelo de destino usando cabeçalhos e amostras reais.
Regra absoluta: só preencha source_column quando tiver certeza máxima, sem dúvida, sem ambiguidade e com conteúdo equivalente ao campo final.
Se existir qualquer dúvida, concorrência entre colunas, mistura de conteúdo, amostra insuficiente ou correspondência apenas provável, deixe source_column vazio.
Não invente coluna de origem. Só use source_column que exista exatamente na lista de colunas da origem.
Não invente campo de destino. Só use target_column que exista exatamente na lista de colunas do modelo.
Nunca mapeie preço/custo/valor para estoque/quantidade.
Nunca mapeie GTIN/EAN para descrição/nome/título.
Nunca mapeie URL/imagem para descrição, código, marca ou categoria.
Responda no formato JSON puro:
{
  "suggestions": [
    {
      "target_column": "nome exato da coluna do modelo",
      "source_column": "nome exato da coluna de origem ou vazio",
      "confidence": 1.0,
      "reason": "motivo curto com base no conteúdo"
    }
  ]
}
Somente use confidence 1.0 quando tiver certeza máxima. Para qualquer outro caso, use source_column vazio.
""".strip()


def _target_snapshot(target_df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(target_df, pd.DataFrame):
        return {'columns': []}
    return {'columns': [str(column) for column in target_df.columns]}


def _with_engine(result: AIResult, *, engine: str, message: str) -> AIResult:
    data = dict(result.data or {})
    data['engine'] = engine
    return AIResult(ok=result.ok, task=result.task, message=message, data=data, error=result.error)


def _sanitize_suggestions(raw: list[Any], source_df: pd.DataFrame, source_columns: list[str], target_columns: list[str]) -> list[dict[str, Any]]:
    source_set = set(source_columns)
    target_set = set(target_columns)
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    used_sources: set[str] = set()
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

        certainty = None
        if source and confidence >= MIN_OPENAI_CONFIDENCE and source not in used_sources:
            certainty = is_unique_certain_mapping(source_df, target, source)
            if not certainty.ok:
                source = ''
        else:
            source = ''

        if source:
            used_sources.add(source)
        clean.append(
            {
                'target_column': target,
                'source_column': source,
                'confidence': 1.0 if source else 0.0,
                'reason': str(item.get('reason') or (certainty.reason if certainty else 'sem certeza máxima')),
                'engine': 'openai_max_certainty',
                'certainty_reason': certainty.reason if certainty else 'sem certeza máxima',
            }
        )
        seen.add(target)
    return clean


def _merge_openai_over_local(local_result: AIResult, openai_mapping: dict[str, str], openai_suggestions: list[dict[str, Any]]) -> AIResult:
    local_data = dict(local_result.data or {})
    local_mapping = dict(local_data.get('mapping') or {})
    merged: dict[str, str] = {}
    used_sources: set[str] = set()

    for target, source in openai_mapping.items():
        source_text = str(source or '').strip()
        if source_text and source_text not in used_sources:
            merged[str(target)] = source_text
            used_sources.add(source_text)

    for target, source in local_mapping.items():
        target_text = str(target)
        source_text = str(source or '').strip()
        if target_text in merged or not source_text or source_text in used_sources:
            continue
        merged[target_text] = source_text
        used_sources.add(source_text)

    suggestions = list(openai_suggestions)
    suggestions.extend(list(local_data.get('suggestions') or []))
    return AIResult(
        ok=True,
        task='mapping_suggester',
        message=f'{len(merged)} campo(s) sugerido(s): OpenAI quando teve certeza máxima + motor local por conteúdo nas demais colunas.',
        data={'mapping': merged, 'suggestions': suggestions, 'engine': 'openai_plus_semantic_content_local'},
    )


def suggest_mapping_with_openai(source_df: pd.DataFrame, target_df: pd.DataFrame, *, operation: str = '') -> AIResult:
    # O mapeamento inteligente local é a base: ele lê o conteúdo das linhas e não
    # depende da OpenAI estar ligada. OpenAI entra apenas como reforço quando existir.
    local_result = suggest_mapping(source_df, target_df)
    if not ai_is_enabled():
        return _with_engine(local_result, engine='semantic_content_local', message=local_result.message)

    source_columns = [str(column) for column in source_df.columns] if isinstance(source_df, pd.DataFrame) else []
    target_columns = [str(column) for column in target_df.columns] if isinstance(target_df, pd.DataFrame) else []
    if not source_columns or not target_columns:
        return _with_engine(local_result, engine='semantic_content_local_empty_columns', message='Origem ou modelo sem colunas para mapear.')

    settings = get_ai_settings()
    payload = {
        'operation': operation,
        'strict_rule': 'apply only mappings with maximum certainty; otherwise leave source_column empty',
        'source': dataframe_snapshot(source_df, max_rows=12, max_columns=80),
        'target': _target_snapshot(target_df),
        'local_suggestions_for_context_and_fallback': local_result.data.get('suggestions', []) if isinstance(local_result.data, dict) else [],
    }
    openai_result = call_openai_json('mapping_suggester_openai_max_certainty', MAPPING_INSTRUCTIONS, payload, settings=settings)
    if not openai_result.ok:
        return _with_engine(local_result, engine='semantic_content_local_openai_unavailable', message=local_result.message)

    raw_suggestions = openai_result.data.get('suggestions', []) if isinstance(openai_result.data, dict) else []
    suggestions = _sanitize_suggestions(raw_suggestions, source_df, source_columns, target_columns)
    mapping = {
        item['target_column']: item['source_column']
        for item in suggestions
        if item.get('target_column') and item.get('source_column') and float(item.get('confidence') or 0) >= MIN_OPENAI_CONFIDENCE
    }
    mapping = filter_mapping_to_certain(source_df, mapping)
    mapping = {target: source for target, source in mapping.items() if source}
    if not mapping:
        return _with_engine(local_result, engine='semantic_content_local_openai_not_certain', message=local_result.message)

    return _merge_openai_over_local(local_result, mapping, suggestions)


__all__ = ['MIN_OPENAI_CONFIDENCE', 'suggest_mapping_with_openai']
