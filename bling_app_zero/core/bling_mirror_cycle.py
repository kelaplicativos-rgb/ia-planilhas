from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from bling_app_zero.core.bling_mirror_config import MirrorMonitorConfig
from bling_app_zero.core.bling_mirror_extract import read_mirror_site_products
from bling_app_zero.core.bling_mirror_item_snapshot import build_item_snapshot
from bling_app_zero.core.bling_mirror_planner import MirrorPlanConfig, build_mirror_plan, report_summary
from bling_app_zero.core.mirror_read_state import summarize_read_state
from bling_app_zero.engines.fast_site_scraper.constants import FLOW_CAPTURE_MAX_DEPTH, FLOW_CAPTURE_MAX_PAGES, FLOW_CAPTURE_MAX_PRODUCTS
from bling_app_zero.engines.fast_site_scraper.deep_site_capture import discover_deep_product_urls

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_cycle.py'
DEFAULT_CYCLE_BUDGET_SECONDS = 55
MAX_CYCLE_BUDGET_SECONDS = 90


@dataclass(frozen=True)
class MirrorCycleResult:
    ok: bool
    stage: str
    message: str
    site_url: str
    deposit_name: str
    mode: str
    rows_seen: int
    product_urls_found: int
    visited_pages: int
    scanned_pages: int
    ignored_external_links: int
    stopped_by_budget: bool
    stop_reason: str
    max_pages: int
    max_products: int
    max_depth: int
    budget_seconds: int
    started_at: str
    finished_at: str
    extracted_rows: int = 0
    extracted_columns: int = 0
    local_ready_rows: int = 0
    local_review_rows: int = 0
    local_empty_rows: int = 0
    item_snapshot_total: int = 0
    item_snapshot_missing_identity: int = 0
    stock_ready: int = 0
    new_products_ready: int = 0
    pending: int = 0
    skipped: int = 0
    ready_for_compare: bool = False
    ready_for_apply: bool = False
    extract: dict[str, Any] | None = None
    read_state: dict[str, Any] | None = None
    item_snapshot: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _clamp_int(value: object, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value or fallback)
    except Exception:
        number = fallback
    return max(minimum, min(number, maximum))


def _valid_url(value: object) -> bool:
    text = str(value or '').strip().lower()
    return text.startswith(('http://', 'https://')) and '.' in text


def _empty_result(cfg: MirrorMonitorConfig, *, ok: bool, stage: str, message: str, started: str, max_pages: int, max_products: int, max_depth: int, budget: int) -> MirrorCycleResult:
    return MirrorCycleResult(
        ok=ok,
        stage=stage,
        message=message,
        site_url=cfg.site_url,
        deposit_name=cfg.deposit_name,
        mode=cfg.mode,
        rows_seen=0,
        product_urls_found=0,
        visited_pages=0,
        scanned_pages=0,
        ignored_external_links=0,
        stopped_by_budget=False,
        stop_reason='',
        max_pages=max_pages,
        max_products=max_products,
        max_depth=max_depth,
        budget_seconds=budget,
        started_at=started,
        finished_at=_now_iso(),
    )


def run_mirror_discovery_cycle(config: MirrorMonitorConfig | Mapping[str, Any]) -> MirrorCycleResult:
    cfg = config if isinstance(config, MirrorMonitorConfig) else MirrorMonitorConfig(**{key: value for key, value in dict(config or {}).items() if key in MirrorMonitorConfig.__dataclass_fields__})
    cfg = cfg.normalized()
    started = _now_iso()
    max_pages = _clamp_int(cfg.max_products_per_cycle, FLOW_CAPTURE_MAX_PAGES, 1, FLOW_CAPTURE_MAX_PAGES)
    max_products = _clamp_int(cfg.max_products_per_cycle, FLOW_CAPTURE_MAX_PRODUCTS, 1, FLOW_CAPTURE_MAX_PRODUCTS)
    max_depth = _clamp_int(FLOW_CAPTURE_MAX_DEPTH, FLOW_CAPTURE_MAX_DEPTH, 0, FLOW_CAPTURE_MAX_DEPTH)
    budget = _clamp_int(DEFAULT_CYCLE_BUDGET_SECONDS, DEFAULT_CYCLE_BUDGET_SECONDS, 8, MAX_CYCLE_BUDGET_SECONDS)

    if not cfg.enabled:
        return _empty_result(cfg, ok=True, stage='inactive', message='Espelhamento desligado. Ciclo não executado.', started=started, max_pages=max_pages, max_products=max_products, max_depth=max_depth, budget=budget)

    if not _valid_url(cfg.site_url) or not cfg.deposit_name:
        return _empty_result(cfg, ok=False, stage='blocked', message='Configuração incompleta: site válido e depósito são obrigatórios.', started=started, max_pages=max_pages, max_products=max_products, max_depth=max_depth, budget=budget)

    try:
        discovery = discover_deep_product_urls(
            cfg.site_url,
            max_pages=max_pages,
            max_products=max_products,
            max_depth=max_depth,
            budget_seconds=budget,
            progress_callback=None,
        )
        found = len(discovery.product_urls)
        raw_urls = discovery.raw_urls or cfg.site_url
        extract = read_mirror_site_products(cfg, raw_urls=raw_urls)
        extract_payload = extract.to_dict(include_dataframe=False)
        read_state_payload: dict[str, Any] = {}
        item_snapshot_payload: dict[str, Any] = {}
        plan_payload: dict[str, Any] = {}
        summary: dict[str, Any] = {}
        local_ready = 0
        local_review = 0
        local_empty = 0
        snapshot_total = 0
        snapshot_missing_identity = 0
        if extract.ok and extract.rows > 0:
            read_state = summarize_read_state(extract.dataframe, review_only=cfg.mode == 'novos_produtos')
            read_state_payload = read_state.to_dict()
            local_ready = int(read_state.ready_rows or 0)
            local_review = int(read_state.review_rows or 0)
            local_empty = int(read_state.empty_rows or 0)
            item_snapshot = build_item_snapshot(extract.dataframe, limit=cfg.max_products_per_cycle)
            item_snapshot_payload = item_snapshot.to_dict()
            snapshot_total = int(item_snapshot.items_total or 0)
            snapshot_missing_identity = int(item_snapshot.missing_identity or 0)
            plan = build_mirror_plan(
                extract.dataframe,
                MirrorPlanConfig(
                    enabled=True,
                    mode=cfg.mode,
                    site_url=cfg.site_url,
                    deposit_name=cfg.deposit_name,
                    interval_minutes=cfg.interval_minutes,
                    max_rows_per_cycle=cfg.max_products_per_cycle,
                    include_stock=cfg.mode in {'estoque', 'estoque_e_novos'},
                    include_new_products=cfg.mode in {'novos_produtos', 'estoque_e_novos'},
                    simulation_only=True,
                ),
            )
            summary = report_summary(plan)
            plan_payload = {
                'rows_seen': int(summary.get('rows_seen') or 0),
                'stock_ready': int(summary.get('stock_ready') or 0),
                'new_products_ready': int(summary.get('new_products_ready') or 0),
                'pending': int(summary.get('pending') or 0),
                'skipped': int(summary.get('skipped') or 0),
                'simulation_only': True,
            }

        message = (
            f'Ciclo monitorado concluído. URLs: {found}; produtos lidos: {int(extract.rows or 0)}; '
            f'itens identificados: {snapshot_total}; linhas locais prontas: {local_ready}; '
            f'estoque pronto: {int(summary.get("stock_ready") or 0)}; produtos novos: {int(summary.get("new_products_ready") or 0)}; '
            f'pendências: {int(summary.get("pending") or 0)}.'
        )
        if not extract.ok:
            message = f'Descoberta concluída com {found} URL(s), mas a leitura monitorada ainda não retornou dados válidos: {extract.message}'

        return MirrorCycleResult(
            ok=bool(extract.ok or found > 0),
            stage='plan_ready' if extract.ok and plan_payload else 'discovery_done',
            message=message,
            site_url=cfg.site_url,
            deposit_name=cfg.deposit_name,
            mode=cfg.mode,
            rows_seen=int(extract.rows or found),
            product_urls_found=found,
            visited_pages=int(discovery.visited_pages),
            scanned_pages=int(discovery.scanned_pages),
            ignored_external_links=int(discovery.ignored_external_links),
            stopped_by_budget=bool(discovery.stopped_by_budget),
            stop_reason=str(discovery.stop_reason or ''),
            max_pages=max_pages,
            max_products=max_products,
            max_depth=max_depth,
            budget_seconds=budget,
            started_at=started,
            finished_at=_now_iso(),
            extracted_rows=int(extract.rows or 0),
            extracted_columns=int(extract.columns or 0),
            local_ready_rows=local_ready,
            local_review_rows=local_review,
            local_empty_rows=local_empty,
            item_snapshot_total=snapshot_total,
            item_snapshot_missing_identity=snapshot_missing_identity,
            stock_ready=int(summary.get('stock_ready') or 0),
            new_products_ready=int(summary.get('new_products_ready') or 0),
            pending=int(summary.get('pending') or 0),
            skipped=int(summary.get('skipped') or 0),
            ready_for_compare=bool(extract.ok and extract.rows > 0),
            ready_for_apply=False,
            extract=extract_payload,
            read_state=read_state_payload,
            item_snapshot=item_snapshot_payload,
            plan=plan_payload,
        )
    except Exception as exc:
        return MirrorCycleResult(
            ok=False,
            stage='error',
            message=f'Erro no ciclo de monitoramento: {exc}',
            site_url=cfg.site_url,
            deposit_name=cfg.deposit_name,
            mode=cfg.mode,
            rows_seen=0,
            product_urls_found=0,
            visited_pages=0,
            scanned_pages=0,
            ignored_external_links=0,
            stopped_by_budget=False,
            stop_reason=exc.__class__.__name__,
            max_pages=max_pages,
            max_products=max_products,
            max_depth=max_depth,
            budget_seconds=budget,
            started_at=started,
            finished_at=_now_iso(),
        )


__all__ = ['DEFAULT_CYCLE_BUDGET_SECONDS', 'MAX_CYCLE_BUDGET_SECONDS', 'MirrorCycleResult', 'run_mirror_discovery_cycle']
