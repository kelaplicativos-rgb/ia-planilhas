from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from bling_app_zero.core.bling_mirror_config import MirrorMonitorConfig
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
    ready_for_compare: bool = False
    ready_for_apply: bool = False
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


def run_mirror_discovery_cycle(config: MirrorMonitorConfig | Mapping[str, Any]) -> MirrorCycleResult:
    cfg = config if isinstance(config, MirrorMonitorConfig) else MirrorMonitorConfig(**{key: value for key, value in dict(config or {}).items() if key in MirrorMonitorConfig.__dataclass_fields__})
    cfg = cfg.normalized()
    started = _now_iso()
    max_pages = _clamp_int(cfg.max_products_per_cycle, FLOW_CAPTURE_MAX_PAGES, 1, FLOW_CAPTURE_MAX_PAGES)
    max_products = _clamp_int(cfg.max_products_per_cycle, FLOW_CAPTURE_MAX_PRODUCTS, 1, FLOW_CAPTURE_MAX_PRODUCTS)
    max_depth = _clamp_int(FLOW_CAPTURE_MAX_DEPTH, FLOW_CAPTURE_MAX_DEPTH, 0, FLOW_CAPTURE_MAX_DEPTH)
    budget = _clamp_int(DEFAULT_CYCLE_BUDGET_SECONDS, DEFAULT_CYCLE_BUDGET_SECONDS, 8, MAX_CYCLE_BUDGET_SECONDS)

    if not cfg.enabled:
        return MirrorCycleResult(
            ok=True,
            stage='inactive',
            message='Espelhamento desligado. Ciclo não executado.',
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

    if not _valid_url(cfg.site_url) or not cfg.deposit_name:
        return MirrorCycleResult(
            ok=False,
            stage='blocked',
            message='Configuração incompleta: site válido e depósito são obrigatórios.',
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
        return MirrorCycleResult(
            ok=True,
            stage='discovery_done',
            message=f'Ciclo de monitoramento executado. {found} URL(s) provável(is) de produto localizada(s). Comparação com Bling ainda não aplicada neste estágio.',
            site_url=cfg.site_url,
            deposit_name=cfg.deposit_name,
            mode=cfg.mode,
            rows_seen=found,
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
            ready_for_compare=found > 0,
            ready_for_apply=False,
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
