from __future__ import annotations

import pandas as pd

from bling_app_zero.ai.ai_config import ai_is_enabled
from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.core.mapping_super_assistant import safe_default_for_target, super_auto_map_columns
from bling_app_zero.ui.mapping_constants import PRICE_TARGET_ALIASES


def force_price_suggestion(target: str, source_columns: list[str], suggested: str) -> str:
    if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
        return 'Preço de venda'
    return suggested


def _target_columns(model: pd.DataFrame) -> list[str]:
    if not isinstance(model, pd.DataFrame):
        return []
    return [str(column) for column in model.columns]


def _valid_source_columns(df_source: pd.DataFrame) -> set[str]:
    if not isinstance(df_source, pd.DataFrame):
        return set()
    return {str(column) for column in df_source.columns}


def _local_super_mapping(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
    auto_mapping = super_auto_map_columns(df_source, model)
    for target, selected in list(auto_mapping.items()):
        default_value = safe_default_for_target(target)
        if default_value:
            auto_mapping[target] = ''
            continue
        auto_mapping[target] = force_price_suggestion(target, source_columns, selected)
    return auto_mapping


def _merge_openai_mapping(
    *,
    local_mapping: dict[str, str],
    openai_mapping: dict[str, str],
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    source_columns: list[str],
) -> dict[str, str]:
    """Mescla OpenAI validada com o mapeamento local sem inventar campos.

    Regra segura:
    - modelo local sempre é a base;
    - OpenAI só substitui quando retornou coluna de origem existente;
    - campos com valor padrão seguro continuam vazios para o preenchimento interno;
    - preço calculado continua tendo prioridade quando existir "Preço de venda".
    """
    source_set = _valid_source_columns(df_source)
    targets = set(_target_columns(model))
    merged = dict(local_mapping)

    for target, source in openai_mapping.items():
        target_name = str(target or '').strip()
        source_name = str(source or '').strip()
        if not target_name or target_name not in targets:
            continue
        if safe_default_for_target(target_name):
            merged[target_name] = ''
            continue
        if not source_name or source_name not in source_set:
            continue
        merged[target_name] = force_price_suggestion(target_name, source_columns, source_name)

    return merged


def _openai_validated_mapping(df_source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
    if not ai_is_enabled():
        return {}
    try:
        result = suggest_mapping_with_openai(df_source, model, operation='universal')
    except Exception:
        return {}
    data = result.data if isinstance(result.data, dict) else {}
    if str(data.get('engine') or '') != 'openai_validated':
        return {}
    mapping = data.get('mapping')
    return {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}


def build_super_mapping(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
    """Gera sugestão inicial do mapeamento principal.

    BLINGFIX IA Real:
    - antes o fluxo principal usava somente o motor local;
    - agora o motor local continua sendo a base segura;
    - se a IA Real estiver ativada e pronta na sidebar, a OpenAI revisa/melhora
      a sugestão inicial;
    - se a IA falhar, estiver desligada, sem chave ou retornar algo inválido, o
      sistema segue com o mapeamento local sem travar o usuário.
    """
    local_mapping = _local_super_mapping(df_source, model, source_columns)
    openai_mapping = _openai_validated_mapping(df_source, model)
    if not openai_mapping:
        return local_mapping
    return _merge_openai_mapping(
        local_mapping=local_mapping,
        openai_mapping=openai_mapping,
        df_source=df_source,
        model=model,
        source_columns=source_columns,
    )


def build_stock_auto_mapping(df_source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
    auto_mapping = build_super_mapping(df_source, model, [str(column) for column in df_source.columns] if isinstance(df_source, pd.DataFrame) else [])
    for target in [str(column) for column in model.columns]:
        if 'deposito' in target.lower() or 'depósito' in target.lower():
            auto_mapping[target] = ''
    return auto_mapping


__all__ = [
    'build_stock_auto_mapping',
    'build_super_mapping',
    'force_price_suggestion',
]