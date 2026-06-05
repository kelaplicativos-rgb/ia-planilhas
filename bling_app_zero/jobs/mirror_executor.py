from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from bling_app_zero.core.bling_mirror_config import MirrorMonitorStatus
from bling_app_zero.core.bling_mirror_cycle import run_mirror_discovery_cycle
from bling_app_zero.core.bling_mirror_store import (
    append_mirror_run,
    load_persistent_config,
    save_persistent_status,
)

RESPONSIBLE_FILE = 'bling_app_zero/jobs/mirror_executor.py'
EXECUTION_MODE_ENV = 'BLING_MIRROR_EXECUTION_MODE'
MODE_MONITOR = 'monitor'
MODE_APPLY_STOCK = 'apply_stock'
MODE_APPLY_FULL = 'apply_full'


@dataclass(frozen=True)
class MirrorExecutorResult:
    ok: bool
    enabled: bool
    execution_mode: str
    state: str
    message: str
    site_url: str
    deposit_name: str
    mode: str
    interval_minutes: int
    max_products_per_cycle: int
    stock_auto_allowed: bool
    new_products_review_only: bool
    require_preview: bool
    monitor_only: bool
    started_at: str
    finished_at: str
    next_run_at: str
    cycle: dict[str, Any] | None = None
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec='seconds')


def _execution_mode(cli_mode: str = '') -> str:
    mode = str(cli_mode or os.getenv(EXECUTION_MODE_ENV, MODE_MONITOR)).strip().lower()
    if mode not in {MODE_MONITOR, MODE_APPLY_STOCK, MODE_APPLY_FULL}:
        return MODE_MONITOR
    return mode


def _result_from_config(*, cfg, mode: str, state: str, message: str, ok: bool, started: datetime, next_run_at: str, cycle: dict[str, Any] | None = None) -> MirrorExecutorResult:
    return MirrorExecutorResult(
        ok=ok,
        enabled=bool(cfg.enabled),
        execution_mode=mode,
        state=state,
        message=message,
        site_url=cfg.site_url,
        deposit_name=cfg.deposit_name,
        mode=cfg.mode,
        interval_minutes=cfg.interval_minutes,
        max_products_per_cycle=cfg.max_products_per_cycle,
        stock_auto_allowed=cfg.stock_auto_allowed,
        new_products_review_only=cfg.new_products_review_only,
        require_preview=cfg.require_preview,
        monitor_only=cfg.monitor_only,
        started_at=_iso(started),
        finished_at=_iso(_now()),
        next_run_at=next_run_at,
        cycle=cycle,
    )


def _persist_result(result: MirrorExecutorResult) -> MirrorExecutorResult:
    cycle = result.cycle or {}
    save_persistent_status(
        MirrorMonitorStatus(
            state=result.state,
            last_run_at=result.finished_at,
            next_run_at=result.next_run_at,
            last_message=result.message,
            last_rows_seen=int(cycle.get('extracted_rows') or cycle.get('rows_seen') or cycle.get('product_urls_found') or 0),
            last_stock_ready=int(cycle.get('stock_ready') or 0),
            last_new_products_ready=int(cycle.get('new_products_ready') or 0),
            last_pending=int(cycle.get('pending') or 0),
            last_skipped=int(cycle.get('skipped') or 0),
        )
    )
    append_mirror_run(result.to_dict())
    return result


def run_once(*, execution_mode: str = '') -> MirrorExecutorResult:
    started = _now()
    cfg = load_persistent_config()
    mode = _execution_mode(execution_mode)
    next_run = started + timedelta(minutes=cfg.interval_minutes)

    if not cfg.enabled:
        result = _result_from_config(
            cfg=cfg,
            mode=mode,
            state='inactive',
            message='Espelhamento desligado. Nenhum ciclo executado.',
            ok=True,
            started=started,
            next_run_at='',
        )
        return _persist_result(result)

    if not cfg.site_url or not cfg.deposit_name:
        result = _result_from_config(
            cfg=cfg,
            mode=mode,
            state='blocked',
            message='Configuração incompleta: informe site e depósito antes do executor automático.',
            ok=False,
            started=started,
            next_run_at=_iso(next_run),
        )
        return _persist_result(result)

    cycle = run_mirror_discovery_cycle(cfg)
    cycle_payload = cycle.to_dict()

    if cfg.monitor_only or mode == MODE_MONITOR:
        result = _result_from_config(
            cfg=cfg,
            mode=MODE_MONITOR,
            state='monitoring_enabled' if cycle.ok else cycle.stage,
            message=cycle.message,
            ok=bool(cycle.ok),
            started=started,
            next_run_at=_iso(next_run),
            cycle=cycle_payload,
        )
        return _persist_result(result)

    if mode in {MODE_APPLY_STOCK, MODE_APPLY_FULL} and not cfg.stock_auto_allowed:
        result = _result_from_config(
            cfg=cfg,
            mode=mode,
            state='blocked',
            message='Aplicação automática bloqueada: estoque automático ainda não foi permitido na configuração.',
            ok=False,
            started=started,
            next_run_at=_iso(next_run),
            cycle=cycle_payload,
        )
        return _persist_result(result)

    result = _result_from_config(
        cfg=cfg,
        mode=mode,
        state='not_implemented',
        message='Ciclo monitorado gerou leitura/plano, mas comparação com Bling e envio por API ainda estão bloqueados até o próximo BLINGFIX.',
        ok=False,
        started=started,
        next_run_at=_iso(next_run),
        cycle=cycle_payload,
    )
    return _persist_result(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Executor agendável do espelhamento Bling.')
    parser.add_argument('--mode', default='', choices=[MODE_MONITOR, MODE_APPLY_STOCK, MODE_APPLY_FULL, ''], help='Modo de execução. Padrão: monitor.')
    args = parser.parse_args(argv)
    result = run_once(execution_mode=args.mode)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0 if result.ok else 2


if __name__ == '__main__':
    raise SystemExit(main())


__all__ = [
    'EXECUTION_MODE_ENV',
    'MODE_APPLY_FULL',
    'MODE_APPLY_STOCK',
    'MODE_MONITOR',
    'MirrorExecutorResult',
    'main',
    'run_once',
]
