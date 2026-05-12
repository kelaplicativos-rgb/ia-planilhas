from __future__ import annotations

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, StoreProfile, TablePayload
from bling_app_zero.v2.exporter import EXPORT_CLEAN_SPEC
from bling_app_zero.v2.multistore_prices import MULTISTORE_PRICE_SPEC
from bling_app_zero.v2.runner import V2Runner


def build_price_runner() -> V2Runner:
    runner = V2Runner()
    runner.register(MULTISTORE_PRICE_SPEC)
    runner.register(EXPORT_CLEAN_SPEC)
    return runner


def build_price_payload(df: pd.DataFrame, profile: StoreProfile, config: dict | None = None) -> TablePayload:
    return TablePayload(
        operation='preco',
        stage='calculate',
        df=df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(),
        store_profile=profile,
        config=dict(config or {}),
        metadata={'flow': 'price_multistore_v2'},
    )


def run_price_flow(df: pd.DataFrame, profile: StoreProfile, config: dict | None = None) -> ModuleResult:
    runner = build_price_runner()
    calculated = runner.run(build_price_payload(df, profile, config), stage='calculate')
    if not calculated.ok:
        return calculated
    return runner.run(calculated.payload, stage='export')


__all__ = ['build_price_payload', 'build_price_runner', 'run_price_flow']
