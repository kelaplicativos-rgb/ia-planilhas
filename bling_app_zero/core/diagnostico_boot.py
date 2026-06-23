from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = "bling_app_zero/core/diagnostico_boot.py"
BOOT_EVENTS_KEY = "mapeiaai_boot_diagnostic_events_v1"
BOOT_UPLOADS_KEY = "mapeiaai_boot_uploads_v1"
BOOT_INSTALLED_KEY = "mapeiaai_boot_diagnostics_installed_v1"
BOOT_PATCHED_MODULES_KEY = "mapeiaai_boot_patched_modules_v1"
MODEL_UPLOAD_KEY = "mapeiaai_universal_model_upload"
MODEL_DF_KEY = "mapeiaai_universal_model_df"
BOOT_VERSION = "boot_diag_before_home_20260623_v1"
BOOT_FILE_PATH = Path(tempfile.gettempdir()) / "mapeiaai_boot_diagnostico.jsonl"
TARGET_MODULES = {"bling_app_zero.ui.universal_flow"}
SENSITIVE_KEYWORDS = (
    "password",
    "senha",
    "secret",
    "token",
    "client_secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "credential",
    "credentials",
    "auth",
    "refresh",
)

_FALLBACK_EVENTS: list[dict[str, Any]] = []
_IMPORT_HOOK_INSTALLED = False
_STREAMLIT_PATCH_INSTALLED = False


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _safe_text(value: Any, limit: int = 800) -> str:
    text = str(value if value is not None else "").replace("\x00", "").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _hash_bytes(data: bytes | bytearray | memoryview) -> str:
    raw = bytes(data or b"")
    return hashlib.sha256(raw).hexdigest()[:16]


def _sanitize(value: Any, *, depth: int = 0, key: Any | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if depth > 4:
        return _safe_text(type(value).__name__, 120)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value or b"")
        return {"type": "bytes", "size": len(raw), "sha256_16": _hash_bytes(raw)}
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, item in list(value.items())[:80]:
            safe_key = _safe_text(k, 140)
            out[safe_key] = _sanitize(item, depth=depth + 1, key=k)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:80]]
    if hasattr(value, "shape") and hasattr(value, "columns"):
        try:
            return {
                "type": type(value).__name__,
                "shape": tuple(value.shape),
                "columns": [_safe_text(col, 120) for col in list(value.columns)[:80]],
            }
        except Exception:
            return {"type": type(value).__name__}
    if hasattr(value, "name") and hasattr(value, "size"):
        return _uploaded_meta(value)
    return {"type": type(value).__name__, "repr": _safe_text(value, 240)}


def _streamlit_state() -> Any | None:
    st = sys.modules.get("streamlit")
    if st is None:
        return None
    try:
        return st.session_state
    except Exception:
        return None


def _state_summary(limit: int = 160) -> dict[str, Any]:
    state = _streamlit_state()
    if state is None:
        return {"available": False}
    out: dict[str, Any] = {"available": True, "keys_count": 0, "keys": []}
    try:
        keys = [str(key) for key in state.keys()]
        out["keys_count"] = len(keys)
        out["keys"] = sorted(keys)[:limit]
        for important in (
            "bling_wizard_step",
            "home_wizard_step",
            "home_active_operation_v2",
            "mapear_planilha_sem_api_active",
            MODEL_DF_KEY,
            "home_modelo_universal_df",
            "df_modelo_universal",
            "modelo_universal_df",
        ):
            if important in state:
                out[important] = _sanitize(state.get(important), key=important)
    except Exception as exc:
        out["summary_error"] = _safe_text(exc, 220)
    return out


def _append_event(event: dict[str, Any]) -> None:
    state = _streamlit_state()
    if state is None:
        _FALLBACK_EVENTS.append(event)
        if len(_FALLBACK_EVENTS) > 800:
            del _FALLBACK_EVENTS[:-800]
        return
    try:
        events = state.get(BOOT_EVENTS_KEY, [])
        if not isinstance(events, list):
            events = []
        events.extend(_FALLBACK_EVENTS)
        _FALLBACK_EVENTS.clear()
        events.append(event)
        if len(events) > 800:
            del events[:-800]
        state[BOOT_EVENTS_KEY] = events
    except Exception:
        _FALLBACK_EVENTS.append(event)


def _persist_event(event: dict[str, Any]) -> None:
    try:
        BOOT_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with BOOT_FILE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def boot_event(action: str, *, area: str = "BOOT", step: str | None = None, status: str = "INFO", details: dict[str, Any] | None = None) -> None:
    state = _streamlit_state()
    current_step = step
    if current_step is None and state is not None:
        try:
            current_step = str(state.get("bling_wizard_step") or state.get("home_wizard_step") or "")
        except Exception:
            current_step = ""
    event = {
        "timestamp": _now_iso(),
        "area": _safe_text(area, 80).upper(),
        "step": _safe_text(current_step or "", 80),
        "action": _safe_text(action, 180),
        "status": _safe_text(status or "INFO", 40).upper(),
        "details": _sanitize({"boot_version": BOOT_VERSION, **(details or {})}),
    }
    _append_event(event)
    _persist_event(event)
    try:
        from bling_app_zero.core.audit import add_audit_event

        add_audit_event(
            f"bootdiag_{event['action']}",
            area=event["area"],
            step=event["step"] or None,
            status=event["status"],
            details={"from_boot_diag": True, **event["details"]},
        )
    except Exception:
        pass


def boot_exception(exc: BaseException, phase: str, *, details: dict[str, Any] | None = None) -> None:
    tb = traceback.extract_tb(exc.__traceback__)
    frames = [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name, "code": _safe_text(frame.line, 260)}
        for frame in tb[-12:]
    ]
    boot_event(
        "exception_captured_before_or_during_ui",
        area="BOOT",
        status="ERRO",
        details={
            "phase": phase,
            "exception_type": type(exc).__name__,
            "exception_message": _safe_text(exc, 900),
            "traceback_tail": frames,
            "state_summary": _state_summary(),
            **(details or {}),
        },
    )


def _uploaded_meta(uploaded_file: Any) -> dict[str, Any]:
    name = _safe_text(getattr(uploaded_file, "name", "") or "", 240)
    size = getattr(uploaded_file, "size", None)
    content_type = _safe_text(getattr(uploaded_file, "type", "") or "", 160)
    try:
        data = uploaded_file.getvalue()
        byte_size = len(data or b"")
        sha = _hash_bytes(data or b"")
    except Exception:
        byte_size = None
        sha = ""
    extension = ""
    if "." in name:
        extension = name.rsplit(".", 1)[-1].lower().strip()
    return {
        "name": name,
        "size_attr": size,
        "byte_size": byte_size,
        "type": content_type,
        "extension": extension,
        "sha256_16": sha,
    }


def _has_dataframe_columns(value: Any) -> bool:
    try:
        return bool(hasattr(value, "columns") and len(list(value.columns)) > 0)
    except Exception:
        return False


def _record_upload(key: str, label: str, uploaded: Any) -> None:
    state = _streamlit_state()
    if state is None:
        return
    items = uploaded if isinstance(uploaded, list) else [uploaded]
    metas = [_uploaded_meta(item) for item in items if item is not None]
    if not metas:
        return
    try:
        uploads = state.get(BOOT_UPLOADS_KEY, {})
        if not isinstance(uploads, dict):
            uploads = {}
        uploads[key or label or "sem_key"] = metas
        state[BOOT_UPLOADS_KEY] = uploads
        if key == MODEL_UPLOAD_KEY:
            state["mapeiaai_boot_model_upload_seen_v1"] = True
            state["mapeiaai_boot_model_upload_last_meta_v1"] = metas[-1]
    except Exception:
        pass
    boot_event(
        "file_uploader_received_file",
        area="UPLOAD",
        status="OK",
        details={"key": key, "label": label, "files": metas, "state_summary": _state_summary(60)},
    )


def _check_model_gate_blocked(context: str, message: str = "") -> None:
    state = _streamlit_state()
    if state is None:
        return
    try:
        uploads = state.get(BOOT_UPLOADS_KEY, {})
        model_upload = None
        if isinstance(uploads, dict):
            model_upload = uploads.get(MODEL_UPLOAD_KEY)
        has_model = _has_dataframe_columns(state.get(MODEL_DF_KEY))
        if model_upload and not has_model:
            boot_event(
                "modelo_upload_detectado_mas_gate_continua_bloqueado",
                area="MODELO",
                status="ERRO",
                details={
                    "context": context,
                    "message": _safe_text(message, 500),
                    "uploaded_model": model_upload,
                    "model_df_present": has_model,
                    "state_summary": _state_summary(),
                    "diagnosis": "O componente recebeu o arquivo, mas a validação do modelo não gravou mapeiaai_universal_model_df.",
                    "probable_causes": [
                        "excecao_silenciosa_na_leitura_do_xlsx",
                        "read_uploaded_file_retornou_dataframe_sem_colunas",
                        "fallback_resolver_modelo_falhou",
                        "chave_session_state_diferente_da_chave_do_uploader",
                    ],
                },
            )
    except Exception:
        pass


def _patch_streamlit(st: Any) -> None:
    global _STREAMLIT_PATCH_INSTALLED
    if _STREAMLIT_PATCH_INSTALLED or getattr(st, "_mapeiaai_boot_diag_streamlit_patched", False):
        return
    _STREAMLIT_PATCH_INSTALLED = True
    setattr(st, "_mapeiaai_boot_diag_streamlit_patched", True)

    original_file_uploader = st.file_uploader
    original_info = st.info
    original_warning = st.warning
    original_error = st.error
    original_set_page_config = st.set_page_config

    def set_page_config_wrapper(*args: Any, **kwargs: Any):
        boot_event("streamlit_set_page_config_start", area="BOOT", status="OK", details={"args_count": len(args), "kwargs": kwargs})
        try:
            result = original_set_page_config(*args, **kwargs)
            boot_event("streamlit_set_page_config_ok", area="BOOT", status="OK", details={"kwargs": kwargs})
            return result
        except BaseException as exc:
            boot_exception(exc, "streamlit_set_page_config")
            raise

    def file_uploader_wrapper(label: str, *args: Any, **kwargs: Any):
        key = _safe_text(kwargs.get("key", "") or "", 160)
        label_text = _safe_text(label, 260)
        if key == MODEL_UPLOAD_KEY or "modelo" in label_text.casefold():
            boot_event("file_uploader_rendered", area="UPLOAD", status="OK", details={"key": key, "label": label_text})
        try:
            uploaded = original_file_uploader(label, *args, **kwargs)
            if uploaded is not None:
                _record_upload(key, label_text, uploaded)
            return uploaded
        except BaseException as exc:
            boot_exception(exc, "streamlit_file_uploader", details={"key": key, "label": label_text})
            raise

    def info_wrapper(body: Any, *args: Any, **kwargs: Any):
        text = _safe_text(body, 1000)
        if "envie a planilha modelo final" in text.casefold():
            _check_model_gate_blocked("st.info_gate_message", text)
        return original_info(body, *args, **kwargs)

    def warning_wrapper(body: Any, *args: Any, **kwargs: Any):
        text = _safe_text(body, 1000)
        if "modelo" in text.casefold() or "planilha" in text.casefold():
            boot_event("streamlit_warning_visible", area="UI", status="AVISO", details={"message": text})
        return original_warning(body, *args, **kwargs)

    def error_wrapper(body: Any, *args: Any, **kwargs: Any):
        text = _safe_text(body, 1200)
        boot_event("streamlit_error_visible", area="UI", status="ERRO", details={"message": text, "state_summary": _state_summary(80)})
        return original_error(body, *args, **kwargs)

    st.set_page_config = set_page_config_wrapper
    st.file_uploader = file_uploader_wrapper
    st.info = info_wrapper
    st.warning = warning_wrapper
    st.error = error_wrapper
    boot_event("streamlit_boot_patch_installed", area="BOOT", status="OK", details={"responsible_file": RESPONSIBLE_FILE})


def _patch_universal_flow(module: ModuleType) -> None:
    if getattr(module, "_mapeiaai_boot_diag_universal_patched", False):
        return
    setattr(module, "_mapeiaai_boot_diag_universal_patched", True)
    original_read_model_upload = getattr(module, "_read_model_upload", None)
    original_render_model_step = getattr(module, "_render_model_step", None)
    pd = getattr(module, "pd", None)

    def _valid_df(df: Any) -> bool:
        try:
            return bool(pd is not None and isinstance(df, pd.DataFrame) and len(df.columns) > 0)
        except Exception:
            return False

    def _fallback_read(uploaded_file: Any) -> Any:
        name = _safe_text(getattr(uploaded_file, "name", "") or "", 240)
        try:
            data = uploaded_file.getvalue()
        except Exception:
            data = b""
        attempts: list[dict[str, Any]] = []
        try:
            read_uploaded_file = getattr(module, "read_uploaded_file")
            df = read_uploaded_file(uploaded_file).fillna("")
            attempts.append({"method": "read_uploaded_file", "valid": _valid_df(df), "summary": _sanitize(df)})
            if _valid_df(df):
                return df, attempts
        except Exception as exc:
            attempts.append({"method": "read_uploaded_file", "error": _safe_text(exc, 500), "error_type": type(exc).__name__})
        try:
            contract_reader = getattr(module, "_model_contract_from_file")
            df = contract_reader(name, bytes(data or b"")).fillna("")
            attempts.append({"method": "_model_contract_from_file", "valid": _valid_df(df), "summary": _sanitize(df)})
            if _valid_df(df):
                return df, attempts
        except Exception as exc:
            attempts.append({"method": "_model_contract_from_file", "error": _safe_text(exc, 500), "error_type": type(exc).__name__})
        return None, attempts

    if callable(original_read_model_upload):
        def read_model_upload_wrapper(uploaded_file: Any):
            if uploaded_file is None:
                return original_read_model_upload(uploaded_file)
            meta = _uploaded_meta(uploaded_file)
            boot_event("universal_model_upload_read_start", area="MODELO", status="OK", details={"uploaded": meta})
            try:
                df = original_read_model_upload(uploaded_file)
            except BaseException as exc:
                boot_exception(exc, "universal_flow_read_model_upload_original", details={"uploaded": meta})
                df = None
            if _valid_df(df):
                boot_event("universal_model_upload_read_ok", area="MODELO", status="OK", details={"uploaded": meta, "df": _sanitize(df)})
                return df
            recovered, attempts = _fallback_read(uploaded_file)
            if _valid_df(recovered):
                boot_event("universal_model_upload_recovered_after_gate_failure", area="MODELO", status="OK", details={"uploaded": meta, "attempts": attempts, "df": _sanitize(recovered)})
                return recovered
            boot_event(
                "universal_model_upload_read_failed_with_diagnostics",
                area="MODELO",
                status="ERRO",
                details={"uploaded": meta, "attempts": attempts, "state_summary": _state_summary()},
            )
            return df

        module._read_model_upload = read_model_upload_wrapper

    if callable(original_render_model_step):
        def render_model_step_wrapper(*args: Any, **kwargs: Any):
            boot_event("universal_model_step_render_start", area="MODELO", status="OK", details={"state_summary": _state_summary(80)})
            result = original_render_model_step(*args, **kwargs)
            if not _valid_df(result):
                _check_model_gate_blocked("universal_flow._render_model_step_result_none")
            else:
                boot_event("universal_model_step_unlocked", area="MODELO", status="OK", details={"df": _sanitize(result)})
            return result

        module._render_model_step = render_model_step_wrapper

    boot_event("universal_flow_boot_patch_installed", area="BOOT", status="OK", details={"module": getattr(module, "__name__", "")})


def _patch_module(module: ModuleType) -> None:
    name = getattr(module, "__name__", "")
    if name == "bling_app_zero.ui.universal_flow":
        _patch_universal_flow(module)


class _BootDiagLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, "create_module", None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _BootDiagFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in TARGET_MODULES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        if isinstance(spec.loader, _BootDiagLoader):
            return spec
        spec.loader = _BootDiagLoader(spec.loader)
        return spec


def install_import_hook() -> None:
    global _IMPORT_HOOK_INSTALLED
    if _IMPORT_HOOK_INSTALLED:
        return
    _IMPORT_HOOK_INSTALLED = True
    for module_name in list(TARGET_MODULES):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            _patch_module(loaded)
    if not any(isinstance(finder, _BootDiagFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _BootDiagFinder())
    boot_event("boot_import_hook_installed_before_home", area="BOOT", status="OK", details={"targets": sorted(TARGET_MODULES)})


def install_streamlit_boot_diagnostics(st: Any | None = None) -> None:
    if st is not None:
        try:
            st.session_state[BOOT_INSTALLED_KEY] = BOOT_VERSION
        except Exception:
            pass
        _patch_streamlit(st)
    install_import_hook()
    boot_event("diagnostico_boot_nasceu_antes_da_home", area="BOOT", status="OK", details={"responsible_file": RESPONSIBLE_FILE, "pid": os.getpid()})


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
        "responsible_file": RESPONSIBLE_FILE,
        "events": _sanitize(events),
        "state_summary": _state_summary(),
        "boot_file_path": str(BOOT_FILE_PATH),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def render_boot_diagnostic_download(st: Any, exc: BaseException | None = None) -> None:
    if exc is not None:
        try:
            st.error("Erro capturado pelo diagnóstico de boot antes da Home.")
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
    "boot_event",
    "boot_exception",
    "export_boot_diagnostic_json",
    "install_import_hook",
    "install_streamlit_boot_diagnostics",
    "render_boot_diagnostic_download",
]
