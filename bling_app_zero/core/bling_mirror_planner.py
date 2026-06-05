from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.bling_product_update_intelligence import analyze_product_update_need, analyze_stock_update_need
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_planner.py'
MODE_STOCK = 'estoque'
MODE_NEW_PRODUCTS = 'novos_produtos'
MODE_BOTH = 'estoque_e_novos'
DECISION_STOCK = 'ATUALIZAR_ESTOQUE'
DECISION_NEW_PRODUCT = 'CADASTRAR_NOVO_PRODUTO'
DECISION_PENDING = 'PENDENCIA'
DECISION_SKIP = 'PULAR'
DEFAULT_INTERVAL_MINUTES = 15
MIN_INTERVAL_MINUTES = 5
MAX_ROWS_PER_CYCLE = 1500


@dataclass(frozen=True)
class MirrorPlanConfig:
    enabled: bool = False
    mode: str = MODE_BOTH
    site_url: str = ''
    deposit_name: str = ''
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    max_rows_per_cycle: int = MAX_ROWS_PER_CYCLE
    only_when_changed: bool = True
    zero_when_unavailable: bool = True
    include_new_products: bool = True
    include_stock: bool = True
    simulation_only: bool = True

    def normalized(self) -> 'MirrorPlanConfig':
        mode = str(self.mode or MODE_BOTH).strip().lower()
        if mode not in {MODE_STOCK, MODE_NEW_PRODUCTS, MODE_BOTH}:
            mode = MODE_BOTH
        return MirrorPlanConfig(
            enabled=bool(self.enabled),
            mode=mode,
            site_url=str(self.site_url or '').strip(),
            deposit_name=str(self.deposit_name or '').strip(),
            interval_minutes=max(MIN_INTERVAL_MINUTES, int(self.interval_minutes or DEFAULT_INTERVAL_MINUTES)),
            max_rows_per_cycle=max(1, min(int(self.max_rows_per_cycle or MAX_ROWS_PER_CYCLE), MAX_ROWS_PER_CYCLE)),
            only_when_changed=bool(self.only_when_changed),
            zero_when_unavailable=bool(self.zero_when_unavailable),
            include_new_products=bool(self.include_new_products),
            include_stock=bool(self.include_stock),
            simulation_only=bool(self.simulation_only),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


@dataclass(frozen=True)
class MirrorPlanDecision:
    decision: str
    operation: str
    row_number: int
    can_apply: bool
    identity: str
    reason: str
    quality_score: int
    payload: dict[str, Any]
    missing_fields: tuple[str, ...] = tuple()
    risk: str = 'baixo'
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['missing_fields'] = list(self.missing_fields)
        return data


@dataclass(frozen=True)
class MirrorPlanReport:
    config: MirrorPlanConfig
    generated_at: str
    rows_seen: int
    stock_ready: int
    new_products_ready: int
    pending: int
    skipped: int
    decisions: tuple[MirrorPlanDecision, ...]
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return {
            'config': self.config.to_dict(),
            'generated_at': self.generated_at,
            'rows_seen': self.rows_seen,
            'stock_ready': self.stock_ready,
            'new_products_ready': self.new_products_ready,
            'pending': self.pending,
            'skipped': self.skipped,
            'decisions': [item.to_dict() for item in self.decisions],
            'responsible_file': self.responsible_file,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _identity_from_row(row: Mapping[str, Any] | Any) -> str:
    try:
        items = row.items() if isinstance(row, Mapping) else row.to_dict().items()
    except Exception:
        return ''
    normalized = {str(key or '').strip().lower(): str(value or '').strip() for key, value in items}
    for key in ('id_bling', 'id produto bling', 'id', 'id produto', 'codigo', 'código', 'sku', 'gtin', 'ean'):
        value = normalized.get(key, '')
        if value and value.lower() not in {'nan', 'none', 'null'}:
            return value
    for key, value in normalized.items():
        if any(term in key for term in ('codigo', 'código', 'sku', 'gtin', 'ean', 'id')) and value and value.lower() not in {'nan', 'none', 'null'}:
            return value
    return ''


def _stock_decision(row: Mapping[str, Any] | Any, row_number: int) -> MirrorPlanDecision:
    decision = analyze_stock_update_need(row)
    can_apply = bool(decision.should_update and not decision.should_hold)
    return MirrorPlanDecision(
        decision=DECISION_STOCK if can_apply else DECISION_PENDING,
        operation=OP_ESTOQUE,
        row_number=row_number,
        can_apply=can_apply,
        identity=decision.site_identity or _identity_from_row(row),
        reason=decision.reason,
        quality_score=int(decision.quality_score or 0),
        payload=decision.payload if isinstance(decision.payload, dict) else {},
        missing_fields=tuple(decision.missing_quality_fields or ()),
        risk=decision.risk,
    )


def _new_product_decision(row: Mapping[str, Any] | Any, row_number: int) -> MirrorPlanDecision:
    decision = analyze_product_update_need(row, None)
    can_apply = bool(decision.should_create and not decision.should_hold)
    if can_apply:
        label = DECISION_NEW_PRODUCT
    elif decision.should_hold:
        label = DECISION_PENDING
    else:
        label = DECISION_SKIP
    return MirrorPlanDecision(
        decision=label,
        operation=OP_CADASTRO,
        row_number=row_number,
        can_apply=can_apply,
        identity=decision.site_identity or _identity_from_row(row),
        reason=decision.reason,
        quality_score=int(decision.quality_score or 0),
        payload=decision.payload if isinstance(decision.payload, dict) else {},
        missing_fields=tuple(decision.missing_quality_fields or ()),
        risk=decision.risk,
    )


def build_mirror_plan(site_df: pd.DataFrame, config: MirrorPlanConfig | Mapping[str, Any] | None = None) -> MirrorPlanReport:
    if isinstance(config, MirrorPlanConfig):
        cfg = config.normalized()
    elif isinstance(config, Mapping):
        allowed = {key: value for key, value in dict(config).items() if key in MirrorPlanConfig.__dataclass_fields__}
        cfg = MirrorPlanConfig(**allowed).normalized()
    else:
        cfg = MirrorPlanConfig().normalized()

    if not isinstance(site_df, pd.DataFrame) or site_df.empty:
        return MirrorPlanReport(cfg, _now_iso(), 0, 0, 0, 0, 0, tuple())

    df = site_df.head(cfg.max_rows_per_cycle).copy().fillna('')
    decisions: list[MirrorPlanDecision] = []
    for position, (_index, row) in enumerate(df.iterrows(), start=1):
        if cfg.include_stock and cfg.mode in {MODE_STOCK, MODE_BOTH}:
            decisions.append(_stock_decision(row, position))
        if cfg.include_new_products and cfg.mode in {MODE_NEW_PRODUCTS, MODE_BOTH}:
            decisions.append(_new_product_decision(row, position))

    stock_ready = sum(1 for item in decisions if item.decision == DECISION_STOCK and item.can_apply)
    new_ready = sum(1 for item in decisions if item.decision == DECISION_NEW_PRODUCT and item.can_apply)
    pending = sum(1 for item in decisions if item.decision == DECISION_PENDING)
    skipped = sum(1 for item in decisions if item.decision == DECISION_SKIP)
    return MirrorPlanReport(cfg, _now_iso(), len(df), stock_ready, new_ready, pending, skipped, tuple(decisions))


def decisions_dataframe(report: MirrorPlanReport) -> pd.DataFrame:
    rows = []
    for item in report.decisions:
        rows.append(
            {
                'decisao': item.decision,
                'operacao': normalize_operation(item.operation),
                'linha': item.row_number,
                'identificador': item.identity,
                'pode_aplicar': item.can_apply,
                'qualidade': item.quality_score,
                'risco': item.risk,
                'faltando': ', '.join(item.missing_fields),
                'motivo': item.reason,
            }
        )
    return pd.DataFrame(rows)


def report_summary(report: MirrorPlanReport) -> dict[str, Any]:
    return {
        'enabled': report.config.enabled,
        'mode': report.config.mode,
        'simulation_only': report.config.simulation_only,
        'rows_seen': report.rows_seen,
        'stock_ready': report.stock_ready,
        'new_products_ready': report.new_products_ready,
        'pending': report.pending,
        'skipped': report.skipped,
        'interval_minutes': report.config.interval_minutes,
        'max_rows_per_cycle': report.config.max_rows_per_cycle,
        'responsible_file': RESPONSIBLE_FILE,
    }


__all__ = [
    'DECISION_NEW_PRODUCT',
    'DECISION_PENDING',
    'DECISION_SKIP',
    'DECISION_STOCK',
    'DEFAULT_INTERVAL_MINUTES',
    'MAX_ROWS_PER_CYCLE',
    'MIN_INTERVAL_MINUTES',
    'MODE_BOTH',
    'MODE_NEW_PRODUCTS',
    'MODE_STOCK',
    'MirrorPlanConfig',
    'MirrorPlanDecision',
    'MirrorPlanReport',
    'build_mirror_plan',
    'decisions_dataframe',
    'report_summary',
]
