from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.bling_mirror_planner import DECISION_NEW_PRODUCT, DECISION_STOCK, MirrorPlanReport
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_apply.py'


@dataclass(frozen=True)
class MirrorApplyBundle:
    stock_df: pd.DataFrame
    new_products_df: pd.DataFrame
    stock_rows: int
    new_product_rows: int
    pending_rows: int
    ready_rows: int
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return {
            'stock_rows': self.stock_rows,
            'new_product_rows': self.new_product_rows,
            'pending_rows': self.pending_rows,
            'ready_rows': self.ready_rows,
            'responsible_file': self.responsible_file,
        }


def _payloads_for(report: MirrorPlanReport, decision_label: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in report.decisions:
        if item.decision != decision_label or not item.can_apply:
            continue
        payload = dict(item.payload or {})
        if not payload:
            continue
        payload['_mirror_row_number'] = item.row_number
        payload['_mirror_identity'] = item.identity
        payload['_mirror_reason'] = item.reason
        payload['_mirror_operation'] = item.operation
        payloads.append(payload)
    return payloads


def build_apply_bundle(report: MirrorPlanReport) -> MirrorApplyBundle:
    stock_payloads = _payloads_for(report, DECISION_STOCK)
    new_product_payloads = _payloads_for(report, DECISION_NEW_PRODUCT)
    stock_df = pd.DataFrame(stock_payloads).fillna('') if stock_payloads else pd.DataFrame()
    new_products_df = pd.DataFrame(new_product_payloads).fillna('') if new_product_payloads else pd.DataFrame()
    pending_rows = sum(1 for item in report.decisions if not item.can_apply)
    return MirrorApplyBundle(
        stock_df=stock_df,
        new_products_df=new_products_df,
        stock_rows=len(stock_df),
        new_product_rows=len(new_products_df),
        pending_rows=pending_rows,
        ready_rows=len(stock_df) + len(new_products_df),
    )


def bundle_to_frames(bundle: MirrorApplyBundle) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    if isinstance(bundle.stock_df, pd.DataFrame) and not bundle.stock_df.empty:
        frames[OP_ESTOQUE] = bundle.stock_df.copy().fillna('')
    if isinstance(bundle.new_products_df, pd.DataFrame) and not bundle.new_products_df.empty:
        frames[OP_CADASTRO] = bundle.new_products_df.copy().fillna('')
    return frames


def bundle_summary(bundle: MirrorApplyBundle | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(bundle, MirrorApplyBundle):
        return bundle.to_dict()
    return dict(bundle or {})


__all__ = ['MirrorApplyBundle', 'build_apply_bundle', 'bundle_summary', 'bundle_to_frames']
