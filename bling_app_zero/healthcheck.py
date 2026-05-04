from __future__ import annotations

from importlib import import_module


REQUIRED_IMPORTS = [
    "bling_app_zero.ui.step_router",
    "bling_app_zero.ui.mod_kernel",
    "bling_app_zero.ui.hook_bus",
    "bling_app_zero.ui.hook_registry",
    "bling_app_zero.ui.origem.flow",
    "bling_app_zero.ui.precificacao.page",
    "bling_app_zero.ui.mapeamento.page",
    "bling_app_zero.ui.preview.page",
    "bling_app_zero.ui.preview_final_estoque_inteligente",
]

LEGACY_MODULES = [
    "bling_app_zero.ui.origem_dados",
    "bling_app_zero.ui.origem_precificacao",
    "bling_app_zero.ui.origem_mapeamento",
    "bling_app_zero.ui.preview_final",
]

OFFICIAL_MODULES = {
    "origem": "bling_app_zero.ui.origem",
    "precificacao": "bling_app_zero.ui.precificacao",
    "mapeamento": "bling_app_zero.ui.mapeamento",
    "preview_final": "bling_app_zero.ui.preview",
}


def _check_imports(modules: list[str]) -> tuple[list[str], dict[str, str]]:
    ok: list[str] = []
    errors: dict[str, str] = {}
    for module in modules:
        try:
            import_module(module)
            ok.append(module)
        except Exception as exc:
            errors[module] = str(exc)
    return ok, errors


def run_healthcheck() -> dict[str, object]:
    ok, errors = _check_imports(REQUIRED_IMPORTS)
    legacy_ok, legacy_errors = _check_imports(LEGACY_MODULES)
    return {
        "success": not errors,
        "ok": ok,
        "errors": errors,
        "official_modules": OFFICIAL_MODULES,
        "legacy_modules_present": legacy_ok,
        "legacy_modules_errors": legacy_errors,
    }


if __name__ == "__main__":
    result = run_healthcheck()
    print(result)
    raise SystemExit(0 if result["success"] else 1)
