from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_config.py'
MIRROR_CONFIG_KEY = 'bling_mirror_monitor_config_v1'
MIRROR_STATUS_KEY = 'bling_mirror_monitor_status_v1'
MIRROR_MODE_STOCK = 'estoque'
MIRROR_MODE_NEW_PRODUCTS = 'novos_produtos'
MIRROR_MODE_BOTH = 'estoque_e_novos'
MIN_INTERVAL_MINUTES = 5
DEFAULT_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 240
MAX_PRODUCTS_PER_CYCLE = 1500


@dataclass(frozen=True)
class MirrorMonitorConfig:
    enabled: bool = False
    site_url: str = ''
    deposit_name: str = ''
    mode: str = MIRROR_MODE_STOCK
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    max_products_per_cycle: int = MAX_PRODUCTS_PER_CYCLE
    stock_auto_allowed: bool = False
    new_products_review_only: bool = True
    require_preview: bool = True
    monitor_only: bool = True
    updated_at: str = ''

    def normalized(self) -> 'MirrorMonitorConfig':
        mode = str(self.mode or MIRROR_MODE_STOCK).strip().lower()
        if mode not in {MIRROR_MODE_STOCK, MIRROR_MODE_NEW_PRODUCTS, MIRROR_MODE_BOTH}:
            mode = MIRROR_MODE_STOCK
        interval = int(self.interval_minutes or DEFAULT_INTERVAL_MINUTES)
        interval = max(MIN_INTERVAL_MINUTES, min(interval, MAX_INTERVAL_MINUTES))
        max_products = int(self.max_products_per_cycle or MAX_PRODUCTS_PER_CYCLE)
        max_products = max(1, min(max_products, MAX_PRODUCTS_PER_CYCLE))
        return MirrorMonitorConfig(
            enabled=bool(self.enabled),
            site_url=str(self.site_url or '').strip(),
            deposit_name=str(self.deposit_name or '').strip(),
            mode=mode,
            interval_minutes=interval,
            max_products_per_cycle=max_products,
            stock_auto_allowed=bool(self.stock_auto_allowed),
            new_products_review_only=True,
            require_preview=True,
            monitor_only=True,
            updated_at=str(self.updated_at or '').strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


@dataclass(frozen=True)
class MirrorMonitorStatus:
    state: str = 'inactive'
    last_run_at: str = ''
    next_run_at: str = ''
    last_message: str = ''
    last_rows_seen: int = 0
    last_stock_ready: int = 0
    last_new_products_ready: int = 0
    last_pending: int = 0
    last_skipped: int = 0
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec='seconds')


def _parse_dt(value: object) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except Exception:
        return None


def config_from_mapping(values: Mapping[str, Any] | None = None) -> MirrorMonitorConfig:
    data = dict(values or {})
    allowed = {key: data.get(key) for key in MirrorMonitorConfig.__dataclass_fields__.keys() if key in data}
    return MirrorMonitorConfig(**allowed).normalized()


def current_mirror_config() -> MirrorMonitorConfig:
    return config_from_mapping(st.session_state.get(MIRROR_CONFIG_KEY) if isinstance(st.session_state.get(MIRROR_CONFIG_KEY), Mapping) else {})


def save_mirror_config(config: MirrorMonitorConfig | Mapping[str, Any]) -> MirrorMonitorConfig:
    cfg = config if isinstance(config, MirrorMonitorConfig) else config_from_mapping(config)
    cfg = cfg.normalized()
    if not cfg.updated_at:
        cfg = MirrorMonitorConfig(**{**cfg.to_dict(), 'updated_at': _iso(_now())}).normalized()
    st.session_state[MIRROR_CONFIG_KEY] = cfg.to_dict()
    st.session_state[MIRROR_STATUS_KEY] = build_status_for_config(cfg).to_dict()
    return cfg


def build_status_for_config(config: MirrorMonitorConfig | Mapping[str, Any]) -> MirrorMonitorStatus:
    cfg = config if isinstance(config, MirrorMonitorConfig) else config_from_mapping(config)
    cfg = cfg.normalized()
    state = 'monitoring_enabled' if cfg.enabled else 'inactive'
    last_status_raw = st.session_state.get(MIRROR_STATUS_KEY)
    previous = dict(last_status_raw) if isinstance(last_status_raw, Mapping) else {}
    last_run_at = str(previous.get('last_run_at') or '')
    base = _parse_dt(last_run_at) or _now()
    next_run_at = _iso(base + timedelta(minutes=cfg.interval_minutes)) if cfg.enabled else ''
    message = 'Monitoramento configurado. Execução recorrente externa ainda não ativada.' if cfg.enabled else 'Monitoramento desligado.'
    return MirrorMonitorStatus(
        state=state,
        last_run_at=last_run_at,
        next_run_at=next_run_at,
        last_message=message,
        last_rows_seen=int(previous.get('last_rows_seen') or 0),
        last_stock_ready=int(previous.get('last_stock_ready') or 0),
        last_new_products_ready=int(previous.get('last_new_products_ready') or 0),
        last_pending=int(previous.get('last_pending') or 0),
        last_skipped=int(previous.get('last_skipped') or 0),
    )


def current_mirror_status() -> MirrorMonitorStatus:
    cfg = current_mirror_config()
    raw = st.session_state.get(MIRROR_STATUS_KEY)
    if not isinstance(raw, Mapping):
        return build_status_for_config(cfg)
    return MirrorMonitorStatus(
        state=str(raw.get('state') or ('monitoring_enabled' if cfg.enabled else 'inactive')),
        last_run_at=str(raw.get('last_run_at') or ''),
        next_run_at=str(raw.get('next_run_at') or ''),
        last_message=str(raw.get('last_message') or ''),
        last_rows_seen=int(raw.get('last_rows_seen') or 0),
        last_stock_ready=int(raw.get('last_stock_ready') or 0),
        last_new_products_ready=int(raw.get('last_new_products_ready') or 0),
        last_pending=int(raw.get('last_pending') or 0),
        last_skipped=int(raw.get('last_skipped') or 0),
    )


def update_status_from_summary(summary: Mapping[str, Any]) -> MirrorMonitorStatus:
    cfg = current_mirror_config()
    now = _now()
    status = MirrorMonitorStatus(
        state='monitoring_enabled' if cfg.enabled else 'inactive',
        last_run_at=_iso(now),
        next_run_at=_iso(now + timedelta(minutes=cfg.interval_minutes)) if cfg.enabled else '',
        last_message='Última simulação registrada no monitoramento.',
        last_rows_seen=int(summary.get('rows_seen') or 0),
        last_stock_ready=int(summary.get('stock_ready') or 0),
        last_new_products_ready=int(summary.get('new_products_ready') or 0),
        last_pending=int(summary.get('pending') or 0),
        last_skipped=int(summary.get('skipped') or 0),
    )
    st.session_state[MIRROR_STATUS_KEY] = status.to_dict()
    return status


def mirror_monitor_payload() -> dict[str, Any]:
    return {
        'config': current_mirror_config().to_dict(),
        'status': current_mirror_status().to_dict(),
        'responsible_file': RESPONSIBLE_FILE,
    }


__all__ = [
    'DEFAULT_INTERVAL_MINUTES',
    'MAX_INTERVAL_MINUTES',
    'MAX_PRODUCTS_PER_CYCLE',
    'MIN_INTERVAL_MINUTES',
    'MIRROR_CONFIG_KEY',
    'MIRROR_MODE_BOTH',
    'MIRROR_MODE_NEW_PRODUCTS',
    'MIRROR_MODE_STOCK',
    'MIRROR_STATUS_KEY',
    'MirrorMonitorConfig',
    'MirrorMonitorStatus',
    'build_status_for_config',
    'config_from_mapping',
    'current_mirror_config',
    'current_mirror_status',
    'mirror_monitor_payload',
    'save_mirror_config',
    'update_status_from_summary',
]
