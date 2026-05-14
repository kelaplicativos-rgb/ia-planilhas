from __future__ import annotations

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, StoreProfile, TablePayload
from bling_app_zero.v2.exporter import EXPORT_CLEAN_SPEC, to_csv_bytes
from bling_app_zero.v2.multistore_prices import MULTISTORE_PRICE_SPEC
from bling_app_zero.v2.price_multistore.detector import detect_multistore_model
from bling_app_zero.v2.price_multistore.matcher import merge_source_cost
from bling_app_zero.v2.price_multistore.validator import has_blocking_errors, validate_after_calculation, validate_before_calculation
from bling_app_zero.v2.runner import V2Runner

COST_COLUMN_INTERNAL = '_v2_custo_base'


def build_runner() -> V2Runner:
    runner = V2Runner()
    runner.register(MULTISTORE_PRICE_SPEC)
    runner.register(EXPORT_CLEAN_SPEC)
    return runner


def prepare_multistore_table(
    model_df: pd.DataFrame,
    source_df: pd.DataFrame | None,
    source_cost_column: str = '',
    model_identifier_column: str = '',
    source_identifier_column: str = '',
) -> pd.DataFrame:
    model = model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame()
    if isinstance(source_df, pd.DataFrame) and not source_df.empty and source_cost_column:
        return merge_source_cost(
            model,
            source_df,
            source_cost_column,
            COST_COLUMN_INTERNAL,
            model_identifier_column=model_identifier_column,
            source_identifier_column=source_identifier_column,
        )
    if COST_COLUMN_INTERNAL not in model.columns:
        model[COST_COLUMN_INTERNAL] = ''
    return model.fillna('')


def run_multistore_price_flow(
    model_df: pd.DataFrame,
    profile: StoreProfile,
    source_df: pd.DataFrame | None = None,
    source_cost_column: str = '',
    pricing_rules: dict | None = None,
    model_identifier_column: str = '',
    source_identifier_column: str = '',
) -> ModuleResult:
    detection = detect_multistore_model(model_df)
    if not detection.is_multistore:
        payload = TablePayload(operation='preco', stage='input', df=model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame(), store_profile=profile)
        return ModuleResult(False, payload, detection.message, errors=detection.missing)

    working_df = prepare_multistore_table(
        model_df,
        source_df,
        source_cost_column,
        model_identifier_column=model_identifier_column,
        source_identifier_column=source_identifier_column,
    )
    issues = validate_before_calculation(working_df)
    if has_blocking_errors(issues):
        payload = TablePayload(operation='preco', stage='validate', df=working_df, store_profile=profile)
        return ModuleResult(False, payload, 'Erros encontrados antes do calculo.', errors=tuple(issue.message for issue in issues))

    config = {'pricing_rules': dict(pricing_rules or {})}
    payload = TablePayload(operation='preco', stage='calculate', df=working_df, store_profile=profile, config=config)
    calculated = build_runner().run(payload, stage='calculate')
    if not calculated.ok:
        return calculated

    issues_after = validate_after_calculation(calculated.payload.df)
    if has_blocking_errors(issues_after):
        return ModuleResult(False, calculated.payload, 'Erros encontrados apos o calculo.', errors=tuple(issue.message for issue in issues_after))

    return build_runner().run(calculated.payload, stage='export')


def multistore_result_to_csv(result: ModuleResult) -> bytes:
    if not result.ok:
        return b''
    return to_csv_bytes(result.payload.df)


__all__ = ['COST_COLUMN_INTERNAL', 'build_runner', 'multistore_result_to_csv', 'prepare_multistore_table', 'run_multistore_price_flow']