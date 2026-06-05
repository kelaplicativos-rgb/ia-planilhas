from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_cycle_diff.py'


@dataclass(frozen=True)
class MirrorCycleDiff:
    ok: bool
    has_previous: bool
    changed: bool
    previous_rows: int
    current_rows: int
    previous_stock_ready: int
    current_stock_ready: int
    previous_new_products_ready: int
    current_new_products_ready: int
    previous_pending: int
    current_pending: int
    message: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int_from(mapping: Mapping[str, Any], key: str) -> int:
    try:
        return int(mapping.get(key) or 0)
    except Exception:
        return 0


def _cycle_from_run(run: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, Mapping):
        return {}
    cycle = run.get('cycle')
    return dict(cycle) if isinstance(cycle, Mapping) else {}


def build_cycle_diff(current_cycle: Mapping[str, Any], previous_run: Mapping[str, Any] | None) -> MirrorCycleDiff:
    current = dict(current_cycle or {})
    previous = _cycle_from_run(previous_run)
    has_previous = bool(previous)
    previous_rows = _int_from(previous, 'extracted_rows') or _int_from(previous, 'rows_seen') or _int_from(previous, 'product_urls_found')
    current_rows = _int_from(current, 'extracted_rows') or _int_from(current, 'rows_seen') or _int_from(current, 'product_urls_found')
    previous_stock_ready = _int_from(previous, 'stock_ready')
    current_stock_ready = _int_from(current, 'stock_ready')
    previous_new_products_ready = _int_from(previous, 'new_products_ready')
    current_new_products_ready = _int_from(current, 'new_products_ready')
    previous_pending = _int_from(previous, 'pending')
    current_pending = _int_from(current, 'pending')
    changed = bool(
        has_previous
        and (
            previous_rows != current_rows
            or previous_stock_ready != current_stock_ready
            or previous_new_products_ready != current_new_products_ready
            or previous_pending != current_pending
        )
    )
    if not has_previous:
        message = 'Primeiro ciclo monitorado: ainda não há execução anterior para comparar.'
    elif changed:
        message = 'Diferença detectada entre a leitura atual e a execução monitorada anterior.'
    else:
        message = 'Nenhuma diferença relevante detectada entre os ciclos monitorados.'
    return MirrorCycleDiff(
        ok=True,
        has_previous=has_previous,
        changed=changed,
        previous_rows=previous_rows,
        current_rows=current_rows,
        previous_stock_ready=previous_stock_ready,
        current_stock_ready=current_stock_ready,
        previous_new_products_ready=previous_new_products_ready,
        current_new_products_ready=current_new_products_ready,
        previous_pending=previous_pending,
        current_pending=current_pending,
        message=message,
    )


__all__ = ['MirrorCycleDiff', 'build_cycle_diff']
