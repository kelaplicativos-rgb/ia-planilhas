from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/pricing_promo_runtime_patch.py'
TARGET_MODULE = 'bling_app_zero.core.product_pricing_center'


def _audit(module: ModuleType, event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='PRECIFICACAO', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _non_blank(series: pd.Series) -> pd.Series:
    return series.fillna('').astype(str).str.strip().ne('')


def _existing_promo_columns(module: ModuleType, df: pd.DataFrame, promo_output_column: str) -> list[str]:
    columns: list[str] = []
    if promo_output_column in df.columns:
        columns.append(str(promo_output_column))
    try:
        for column in module.promotional_price_columns(df.columns):
            if column not in columns:
                columns.append(str(column))
    except Exception:
        pass
    for column in list(getattr(module, 'PROMO_PRICE_TARGET_ALIASES', []) or []):
        if str(column) in df.columns and str(column) not in columns:
            columns.append(str(column))
    return columns


def patch_product_pricing_center(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_pricing_promo_runtime_patched', False):
        return
    original_apply_shared_pricing = module.apply_shared_pricing

    def apply_shared_pricing_promo_safe(
        df: pd.DataFrame,
        cost_column: str,
        output_column: str = module.PRICE_OUTPUT_COLUMN,
        config: dict[str, Any] | None = None,
        channel: str = module.DEFAULT_CHANNEL,
        promo_output_column: str = module.PROMO_PRICE_OUTPUT_COLUMN,
    ) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        existing = df.copy().fillna('')
        existing_promo = {column: existing[column].copy() for column in _existing_promo_columns(module, existing, promo_output_column) if column in existing.columns}
        out = original_apply_shared_pricing(existing, cost_column, output_column, config, channel, promo_output_column)
        if not isinstance(out, pd.DataFrame) or out.empty:
            return out
        normalized = module.normalize_shared_price_config(config)
        promo_percent = float(normalized.get('promo_discount_percent', 0) or 0)
        promo_values = out[promo_output_column] if promo_output_column in out.columns else pd.Series([''] * len(out), index=out.index)
        promo_mask = _non_blank(promo_values)

        if promo_percent <= 0 or not bool(promo_mask.any()):
            # Sem promoção calculada, a calculadora não pode apagar o valor que veio do modelo/origem.
            for column, values in existing_promo.items():
                out[column] = values
            _audit(module, 'pricing_promo_preserved_when_discount_zero', details={'promo_columns': list(existing_promo.keys()), 'promo_discount_percent': promo_percent})
            return out

        # Com promoção ativa, o preço promocional calculado alimenta todos os campos promocionais existentes no modelo.
        target_columns = list(dict.fromkeys([promo_output_column, *existing_promo.keys(), *list(getattr(module, 'PROMO_PRICE_TARGET_ALIASES', []) or [])]))
        for column in target_columns:
            name = str(column)
            if name not in out.columns and name not in existing.columns:
                continue
            if name not in out.columns:
                out[name] = ''
            out.loc[promo_mask, name] = promo_values.loc[promo_mask]
        _audit(module, 'pricing_promo_filled_from_calculator', details={'promo_columns': [str(c) for c in target_columns if str(c) in out.columns], 'promo_discount_percent': promo_percent})
        return out

    module.apply_shared_pricing = apply_shared_pricing_promo_safe
    module._mapeiaai_pricing_promo_runtime_patched = True
    _audit(module, 'pricing_promo_runtime_patch_installed', details={'rule': 'calculadora gera Preco cheio + Preco Promocional; desconto zero preserva promocional existente'})


def _patch_loaded() -> None:
    loaded = sys.modules.get(TARGET_MODULE)
    if loaded is not None:
        patch_product_pricing_center(loaded)


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, 'create_module', None)
        return create_module(spec) if create_module is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        if getattr(module, '__name__', '') == TARGET_MODULE:
            patch_product_pricing_center(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != TARGET_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PatchLoader):
            return spec
        spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    _patch_loaded()
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_product_pricing_center']
