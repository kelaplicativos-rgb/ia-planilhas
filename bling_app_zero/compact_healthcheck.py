from __future__ import annotations

from importlib import import_module


CORE_MODULES = [
    "bling_app_zero.utils.init_app",
    "bling_app_zero.ui.app_core_config",
    "bling_app_zero.ui.app_core_state",
    "bling_app_zero.ui.app_core_layout",
    "bling_app_zero.ui.app_core_flow_safe",
    "bling_app_zero.ui.compact_flow_guard",
    "bling_app_zero.ui.step_router",
    "bling_app_zero.ui.mod_kernel",
    "bling_app_zero.ui.origem",
    "bling_app_zero.ui.mapeamento",
    "bling_app_zero.ui.preview",
    "bling_app_zero.ui.smart_clip_uploader",
    "bling_app_zero.core.file_reader",
    "bling_app_zero.core.csv_reader",
    "bling_app_zero.core.auto_mapper",
]

READER_ENGINES = ["openpyxl", "odf", "pyxlsb", "xlrd", "lxml"]

OFFICIAL_FLOW = {
    "origem": "bling_app_zero.ui.origem.render_origem_dados",
    "mapeamento": "bling_app_zero.ui.mapeamento.render_origem_mapeamento",
    "preview_final": "bling_app_zero.ui.preview.render_preview_final",
}


def _check(modules: list[str]) -> tuple[list[str], dict[str, str]]:
    ok: list[str] = []
    errors: dict[str, str] = {}
    for module in modules:
        try:
            import_module(module)
            ok.append(module)
        except Exception as exc:
            errors[module] = str(exc)
    return ok, errors


def run_compact_healthcheck() -> dict[str, object]:
    core_ok, core_errors = _check(CORE_MODULES)
    engine_ok, engine_errors = _check(READER_ENGINES)
    return {
        "success": not core_errors,
        "core_ok": core_ok,
        "core_errors": core_errors,
        "reader_engines_ok": engine_ok,
        "reader_engines_missing": engine_errors,
        "official_flow": OFFICIAL_FLOW,
    }
