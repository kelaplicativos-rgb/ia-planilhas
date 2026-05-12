from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.features.contracts import FeatureContext, FeatureDefinition, FeatureResult, FeatureScope, FeatureStage
from bling_app_zero.features.registry import list_features
from bling_app_zero.features.state import get_feature_config, is_feature_enabled

RESPONSIBLE_FILE = 'bling_app_zero/features/runtime.py'
FEATURE_RUNTIME_RESULTS_KEY = 'features_runtime_last_results'


def _feature_default_enabled(feature: FeatureDefinition) -> bool:
    return feature.status in {'stable', 'beta'}


def _scope_matches(feature: FeatureDefinition, operation: str) -> bool:
    normalized = str(operation or 'global').strip().lower()
    return feature.scope == 'global' or feature.scope == normalized


def _stage_matches(feature: FeatureDefinition, stage: str) -> bool:
    normalized = str(stage or 'global').strip().lower()
    return feature.stage == 'global' or feature.stage == normalized


def active_features(*, operation: FeatureScope | str = 'global', stage: FeatureStage | str = 'global') -> list[FeatureDefinition]:
    selected: list[FeatureDefinition] = []
    for feature in list_features():
        if feature.status == 'disabled':
            continue
        if not _scope_matches(feature, str(operation)):
            continue
        if not _stage_matches(feature, str(stage)):
            continue
        if not is_feature_enabled(feature.key, default=_feature_default_enabled(feature)):
            continue
        selected.append(feature)
    return selected


def build_feature_context(
    *,
    operation: FeatureScope | str = 'global',
    stage: FeatureStage | str = 'global',
    source_df: pd.DataFrame | None = None,
    model_df: pd.DataFrame | None = None,
    final_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
) -> FeatureContext:
    state = {
        key: value
        for key, value in st.session_state.items()
        if str(key).startswith('feature_') or str(key).endswith('_enabled')
    }
    return FeatureContext(
        operation=str(operation or 'global'),
        stage=str(stage or 'global'),
        source_df=source_df,
        model_df=model_df,
        final_df=final_df,
        config=dict(config or {}),
        state=state,
    )


def _apply_result(result: FeatureResult, context: FeatureContext) -> FeatureContext:
    for key, value in result.state_updates.items():
        st.session_state[key] = value
    return FeatureContext(
        operation=context.operation,
        stage=context.stage,
        source_df=result.source_df if result.source_df is not None else context.source_df,
        model_df=context.model_df,
        final_df=result.final_df if result.final_df is not None else context.final_df,
        config=context.config,
        state=context.state,
    )


def run_feature(feature: FeatureDefinition, context: FeatureContext) -> tuple[FeatureContext, FeatureResult]:
    if feature.runner is None:
        result = FeatureResult(ok=True, message='Módulo sem runner executável; apenas registrado no BLINGMODULE.')
        return context, result

    try:
        module_config = get_feature_config(feature.key)
        merged_context = FeatureContext(
            operation=context.operation,
            stage=context.stage,
            source_df=context.source_df,
            model_df=context.model_df,
            final_df=context.final_df,
            config={**context.config, **module_config},
            state=context.state,
        )
        result = feature.runner(merged_context)
        if not isinstance(result, FeatureResult):
            result = FeatureResult(ok=False, errors=[f'Runner do módulo {feature.key} não retornou FeatureResult.'])
        next_context = _apply_result(result, merged_context)
        return next_context, result
    except Exception as exc:
        add_debug(f'Falha ao executar módulo {feature.key}: {exc}', origin='FEATURES', level='ERRO')
        result = FeatureResult(ok=False, errors=[str(exc) or exc.__class__.__name__])
        return context, result


def run_features_for_stage(
    *,
    operation: FeatureScope | str,
    stage: FeatureStage | str,
    source_df: pd.DataFrame | None = None,
    model_df: pd.DataFrame | None = None,
    final_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
) -> FeatureContext:
    context = build_feature_context(
        operation=operation,
        stage=stage,
        source_df=source_df,
        model_df=model_df,
        final_df=final_df,
        config=config,
    )
    results: list[dict[str, Any]] = []
    features = active_features(operation=operation, stage=stage)

    add_audit_event(
        'features_stage_started',
        area='FEATURES',
        step=str(stage),
        details={
            'operation': str(operation),
            'stage': str(stage),
            'features': [feature.key for feature in features],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    for feature in features:
        context, result = run_feature(feature, context)
        results.append(
            {
                'feature': feature.key,
                'ok': result.ok,
                'message': result.message,
                'warnings': result.warnings,
                'errors': result.errors,
            }
        )
        add_audit_event(
            'feature_executed',
            area='FEATURES',
            step=str(stage),
            status='OK' if result.ok else 'ERRO',
            details={
                'feature': feature.key,
                'operation': str(operation),
                'stage': str(stage),
                'message': result.message,
                'warnings': result.warnings,
                'errors': result.errors,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    st.session_state[FEATURE_RUNTIME_RESULTS_KEY] = results
    return context


__all__ = [
    'FEATURE_RUNTIME_RESULTS_KEY',
    'active_features',
    'build_feature_context',
    'run_feature',
    'run_features_for_stage',
]
