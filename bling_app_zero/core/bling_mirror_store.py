from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from bling_app_zero.core.bling_mirror_config import (
    MirrorMonitorConfig,
    MirrorMonitorStatus,
    config_from_mapping,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_store.py'
MIRROR_STORE_ENV = 'BLING_MIRROR_STORE_PATH'
DEFAULT_STORE_PATH = '.bling_mirror_state.json'


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _store_path() -> Path:
    raw = os.getenv(MIRROR_STORE_ENV, DEFAULT_STORE_PATH)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _empty_payload() -> dict[str, Any]:
    return {
        'version': 1,
        'updated_at': '',
        'config': MirrorMonitorConfig().to_dict(),
        'status': MirrorMonitorStatus().to_dict(),
        'runs': [],
        'responsible_file': RESPONSIBLE_FILE,
    }


def read_mirror_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _empty_payload()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return _empty_payload()
        payload = _empty_payload()
        payload.update(data)
        if not isinstance(payload.get('config'), dict):
            payload['config'] = MirrorMonitorConfig().to_dict()
        if not isinstance(payload.get('status'), dict):
            payload['status'] = MirrorMonitorStatus().to_dict()
        if not isinstance(payload.get('runs'), list):
            payload['runs'] = []
        return payload
    except Exception:
        return _empty_payload()


def write_mirror_store(payload: Mapping[str, Any]) -> dict[str, Any]:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _empty_payload()
    data.update(dict(payload or {}))
    data['updated_at'] = _now_iso()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return data


def load_persistent_config() -> MirrorMonitorConfig:
    payload = read_mirror_store()
    return config_from_mapping(payload.get('config') if isinstance(payload.get('config'), dict) else {})


def save_persistent_config(config: MirrorMonitorConfig | Mapping[str, Any]) -> MirrorMonitorConfig:
    cfg = config if isinstance(config, MirrorMonitorConfig) else config_from_mapping(config)
    cfg = cfg.normalized()
    if not cfg.updated_at:
        cfg = MirrorMonitorConfig(**{**cfg.to_dict(), 'updated_at': _now_iso()}).normalized()
    payload = read_mirror_store()
    payload['config'] = cfg.to_dict()
    payload['status'] = payload.get('status') if isinstance(payload.get('status'), dict) else MirrorMonitorStatus().to_dict()
    write_mirror_store(payload)
    return cfg


def load_persistent_status() -> MirrorMonitorStatus:
    payload = read_mirror_store()
    raw = payload.get('status') if isinstance(payload.get('status'), dict) else {}
    return MirrorMonitorStatus(
        state=str(raw.get('state') or 'inactive'),
        last_run_at=str(raw.get('last_run_at') or ''),
        next_run_at=str(raw.get('next_run_at') or ''),
        last_message=str(raw.get('last_message') or ''),
        last_rows_seen=int(raw.get('last_rows_seen') or 0),
        last_stock_ready=int(raw.get('last_stock_ready') or 0),
        last_new_products_ready=int(raw.get('last_new_products_ready') or 0),
        last_pending=int(raw.get('last_pending') or 0),
        last_skipped=int(raw.get('last_skipped') or 0),
    )


def save_persistent_status(status: MirrorMonitorStatus | Mapping[str, Any]) -> MirrorMonitorStatus:
    if isinstance(status, MirrorMonitorStatus):
        fixed = status
    else:
        raw = dict(status or {})
        fixed = MirrorMonitorStatus(
            state=str(raw.get('state') or 'inactive'),
            last_run_at=str(raw.get('last_run_at') or ''),
            next_run_at=str(raw.get('next_run_at') or ''),
            last_message=str(raw.get('last_message') or ''),
            last_rows_seen=int(raw.get('last_rows_seen') or 0),
            last_stock_ready=int(raw.get('last_stock_ready') or 0),
            last_new_products_ready=int(raw.get('last_new_products_ready') or 0),
            last_pending=int(raw.get('last_pending') or 0),
            last_skipped=int(raw.get('last_skipped') or 0),
        )
    payload = read_mirror_store()
    payload['status'] = fixed.to_dict()
    write_mirror_store(payload)
    return fixed


def append_mirror_run(run_payload: Mapping[str, Any], *, max_runs: int = 80) -> dict[str, Any]:
    payload = read_mirror_store()
    runs = payload.get('runs') if isinstance(payload.get('runs'), list) else []
    item = dict(run_payload or {})
    item.setdefault('created_at', _now_iso())
    item.setdefault('responsible_file', RESPONSIBLE_FILE)
    runs.append(item)
    payload['runs'] = runs[-max(1, int(max_runs or 80)):]
    write_mirror_store(payload)
    return item


def mirror_store_payload() -> dict[str, Any]:
    payload = read_mirror_store()
    payload['store_path'] = str(_store_path())
    payload['responsible_file'] = RESPONSIBLE_FILE
    return payload


__all__ = [
    'DEFAULT_STORE_PATH',
    'MIRROR_STORE_ENV',
    'append_mirror_run',
    'load_persistent_config',
    'load_persistent_status',
    'mirror_store_payload',
    'read_mirror_store',
    'save_persistent_config',
    'save_persistent_status',
    'write_mirror_store',
]
