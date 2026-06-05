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
    item_snapshot_used: bool
    item_new: int
    item_changed: int
    item_removed: int
    item_unchanged: int
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


def _items_by_identity(cycle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    snapshot = cycle.get('item_snapshot') if isinstance(cycle.get('item_snapshot'), Mapping) else {}
    raw_items = snapshot.get('items') if isinstance(snapshot, Mapping) else []
    items: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_items, list):
        return items
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        identity = str(raw.get('identity') or '').strip()
        if not identity:
            continue
        items[identity] = dict(raw)
    return items


def _item_diff(previous: Mapping[str, Any], current: Mapping[str, Any]) -> tuple[bool, int, int, int, int]:
    previous_items = _items_by_identity(previous)
    current_items = _items_by_identity(current)
    used = bool(previous_items or current_items)
    if not used:
        return False, 0, 0, 0, 0
    previous_keys = set(previous_items)
    current_keys = set(current_items)
    new_count = len(current_keys - previous_keys)
    removed_count = len(previous_keys - current_keys)
    changed_count = 0
    unchanged_count = 0
    for key in previous_keys & current_keys:
        if str(previous_items[key].get('signature') or '') != str(current_items[key].get('signature') or ''):
            changed_count += 1
        else:
            unchanged_count += 1
    return True, new_count, changed_count, removed_count, unchanged_count


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
    item_snapshot_used, item_new, item_changed, item_removed, item_unchanged = _item_diff(previous, current)
    counter_changed = bool(
        has_previous
        and (
            previous_rows != current_rows
            or previous_stock_ready != current_stock_ready
            or previous_new_products_ready != current_new_products_ready
            or previous_pending != current_pending
        )
    )
    item_level_changed = bool(item_snapshot_used and (item_new or item_changed or item_removed))
    changed = bool(has_previous and (counter_changed or item_level_changed))
    if not has_previous:
        message = 'Primeiro ciclo monitorado: ainda não há execução anterior para comparar.'
    elif changed and item_snapshot_used:
        message = f'Diferença por item detectada: {item_new} novo(s), {item_changed} alterado(s), {item_removed} removido(s).'
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
        item_snapshot_used=item_snapshot_used,
        item_new=item_new,
        item_changed=item_changed,
        item_removed=item_removed,
        item_unchanged=item_unchanged,
        message=message,
    )


__all__ = ['MirrorCycleDiff', 'build_cycle_diff']
