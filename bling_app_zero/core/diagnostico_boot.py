from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

RESPONSIBLE_FILE = "bling_app_zero/core/diagnostico_boot.py"
BOOT_EVENTS_KEY = "mapeiaai_boot_diagnostic_events_v1"
BOOT_UPLOADS_KEY = "mapeiaai_boot_uploads_v1"
BOOT_INSTALLED_KEY = "mapeiaai_boot_diagnostics_installed_v1"
BOOT_PATCHED_MODULES_KEY = "mapeiaai_boot_patched_modules_v1"
BOOT_VERSION = "boot_diag_disabled_by_default_20260624_v1"

_TRUE_VALUES = {"1", "true", "sim", "yes", "on", "debug", "diagnostico", "diagnóstico"}
_MAX_EVENTS = 80
_FALLBACK_EVENTS: list[dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _enabled_from_env() -> bool:
    return str(os.getenv("MAPEIAAI_BOOT_DIAGNOSTIC", "")).strip().lower() in _TRUE_VALUES


def _streamlit_state() -> Any | None:
    st = sys.modules.get("streamlit")
    if st is None:
        return None
    try:
        return st.session_state
    except Exception:
        return None


def _enabled_from_query(st: Any | None = None) -> bool:
    st = st or sys.modules.get("streamlit")
    if st is None:
        return False
    try:
        for key in ("bootdiag", "diagnostico_boot", "debug_boot"):
            value = st.query_params.get(key)
            if isinstance(value, list):
                value = value[0] if value else ""
            if str(value or "").strip().lower() in _TRUE_VALUES:
                return True
    except Exception:
        return False
    return False


def boot_diagnostics_enabled(st: Any | None = None) -> bool:
    """Boot diagnostics are opt-in only.

    The previous runtime patched Streamlit widgets on every rerun and copied large
    session summaries into the audit log. That helped one investigation, but made
    normal use heavy. Keep this disabled unless support explicitly opens the app
    with ?bootdiag=1 or sets MAPEIAAI_BOOT_DIAGNOSTIC=1.
    """
    return _enabled_from_env() or _enabled_from_query(st)


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value if value is not None else "").replace("\x00", "").strip()
    return text[:limit] + "..." if len(text) > limit else text


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 2:
        return _safe_text(type(value).__name__, 80)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:30]:
            key_text = _safe_text(key, 80)
            lowered = key_text.lower()
            if any(word in lowered for word in ("token", "secret", "senha", "password", "authorization", "cookie")):
                out[key_text] = "[REDACTED]"
            else:
                out[key_text] = _sanitize(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:30]]
    if hasattr(value, "shape") and hasattr(value, "columns"):
        try:
            return {"type": type(value).__name__, "shape": tuple(value.shape), "columns_count": len(list(value.columns))}
        except Exception:
            return {"type": type(value).__name__}
    return _safe_text(type(value).__name__, 120)


def _append_event(event: dict[str, Any]) -> None:
    state = _streamlit_state()
    if state is None:
        _FALLBACK_EVENTS.append(event)
        if len(_FALLBACK_EVENTS) > _MAX_EVENTS:
            del _FALLBACK_EVENTS[:-_MAX_EVENTS]
        return
    try:
        events = state.get(BOOT_EVENTS_KEY, [])
        if not isinstance(events, list):
            events = []
        events.extend(_FALLBACK_EVENTS)
        _FALLBACK_EVENTS.clear()
        events.append(event)
        if len(events) > _MAX_EVENTS:
            del events[:-_MAX_EVENTS]
        state[BOOT_EVENTS_KEY] = events
    except Exception:
        pass


def boot_event(action: str, *, area: str = "BOOT", step: str | None = None, status: str = "INFO", details: dict[str, Any] | None = None) -> None:
    if not boot_diagnostics_enabled():
        return
    event = {
        "timestamp": _now_iso(),
        "area": _safe_text(area, 80).upper(),
        "step": _safe_text(step or "", 80),
        "action": _safe_text(action, 180),
        "status": _safe_text(status or "INFO", 40).upper(),
        "details": _sanitize({"boot_version": BOOT_VERSION, **(details or {})}),
    }
    _append_event(event)


def boot_exception(exc: BaseException, phase: str, *, details: dict[str, Any] | None = None) -> None:
    boot_event(
        "exception_captured_before_or_during_ui",
        area="BOOT",
        status="ERRO",
        details={"phase": phase, "exception_type": type(exc).__name__, "exception_message": _safe_text(exc, 900), **(details or {})},
    )


def install_import_hook() -> None:
    # No-op by default. The old import hook patched universal_flow and created
    # diagnostic events every rerun; the fast model patch now owns that fix.
    boot_event("boot_import_hook_skipped_default_light_mode", area="BOOT", status="INFO")


def install_streamlit_boot_diagnostics(st: Any | None = None) -> None:
    if not boot_diagnostics_enabled(st):
        try:
            if st is not None:
                st.session_state[BOOT_INSTALLED_KEY] = "disabled_default_light_mode"
        except Exception:
            pass
        return
    try:
        if st is not None:
            st.session_state[BOOT_INSTALLED_KEY] = BOOT_VERSION
    except Exception:
        pass
    boot_event("diagnostico_boot_opt_in_enabled", area="BOOT", status="OK", details={"responsible_file": RESPONSIBLE_FILE})


def export_boot_diagnostic_json() -> str:
    state = _streamlit_state()
    events = list(_FALLBACK_EVENTS)
    if state is not None:
        try:
            stored = state.get(BOOT_EVENTS_KEY, [])
            if isinstance(stored, list):
                events.extend(stored)
        except Exception:
            pass
    payload = {
        "generated_at": _now_iso(),
        "boot_version": BOOT_VERSION,
        "boot_diagnostics_enabled": boot_diagnostics_enabled(),
        "responsible_file": RESPONSIBLE_FILE,
        "events": _sanitize(events),
        "note": "Diagnóstico de boot automático desativado por padrão para manter o app rápido. Use ?bootdiag=1 apenas em suporte.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def render_boot_diagnostic_download(st: Any, exc: BaseException | None = None) -> None:
    if exc is not None:
        try:
            st.error("Erro capturado. Gere o diagnóstico técnico apenas se o suporte solicitar.")
            st.exception(exc)
        except Exception:
            pass
    try:
        st.download_button(
            "Baixar diagnóstico de boot do MapeiaAI",
            data=export_boot_diagnostic_json().encode("utf-8"),
            file_name="mapeiaai_diagnostico_boot.json",
            mime="application/json",
            use_container_width=True,
        )
    except Exception:
        pass


__all__ = [
    "BOOT_EVENTS_KEY",
    "BOOT_UPLOADS_KEY",
    "BOOT_VERSION",
    "boot_diagnostics_enabled",
    "boot_event",
    "boot_exception",
    "export_boot_diagnostic_json",
    "install_import_hook",
    "install_streamlit_boot_diagnostics",
    "render_boot_diagnostic_download",
]
