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


def run_healthcheck() -> dict[str, object]:
    ok: list[str] = []
    errors: dict[str, str] = {}
    for module in REQUIRED_IMPORTS:
        try:
            import_module(module)
            ok.append(module)
        except Exception as exc:
            errors[module] = str(exc)
    return {
        "success": not errors,
        "ok": ok,
        "errors": errors,
    }


if __name__ == "__main__":
    result = run_healthcheck()
    print(result)
    raise SystemExit(0 if result["success"] else 1)
