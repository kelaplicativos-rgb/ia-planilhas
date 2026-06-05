from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bling_app_zero.core.bling_mirror_store import mirror_store_payload

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_store_health.py'


@dataclass(frozen=True)
class MirrorStoreHealth:
    ok: bool
    exists: bool
    parent_exists: bool
    readable: bool
    writable_parent: bool
    store_path: str
    runs_total: int
    has_config: bool
    has_status: bool
    message: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_mirror_store_health() -> MirrorStoreHealth:
    payload = mirror_store_payload()
    path_text = str(payload.get('store_path') or '').strip()
    path = Path(path_text) if path_text else Path('')
    exists = bool(path_text and path.exists())
    parent_exists = bool(path_text and path.parent.exists())
    readable = False
    writable_parent = False
    if exists:
        try:
            path.read_text(encoding='utf-8')
            readable = True
        except Exception:
            readable = False
    if parent_exists:
        writable_parent = True
        try:
            probe = path.parent / '.mirror_store_write_probe.tmp'
            probe.write_text('ok', encoding='utf-8')
            probe.unlink(missing_ok=True)
        except Exception:
            writable_parent = False
    runs = payload.get('runs') if isinstance(payload.get('runs'), list) else []
    has_config = isinstance(payload.get('config'), dict)
    has_status = isinstance(payload.get('status'), dict)
    ok = bool(parent_exists and writable_parent and has_config and has_status)
    message = 'Store persistente pronto para leitura/gravação.' if ok else 'Store persistente precisa de revisão no ambiente.'
    return MirrorStoreHealth(
        ok=ok,
        exists=exists,
        parent_exists=parent_exists,
        readable=readable,
        writable_parent=writable_parent,
        store_path=path_text,
        runs_total=len(runs),
        has_config=has_config,
        has_status=has_status,
        message=message,
    )


__all__ = ['MirrorStoreHealth', 'check_mirror_store_health']
