from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Iterable


@dataclass
class ArchitectureCheckResult:
    ok: bool
    checked: list[str]
    errors: list[str]


CRITICAL_IMPORTS = [
    "bling_app_zero.ui.step_router",
    "bling_app_zero.ui.mod_kernel",
    "bling_app_zero.ui.health_panel",
    "bling_app_zero.ui.origem",
    "bling_app_zero.ui.origem.flow",
    "bling_app_zero.ui.precificacao",
    "bling_app_zero.ui.precificacao.page",
    "bling_app_zero.ui.mapeamento",
    "bling_app_zero.ui.mapeamento.page",
    "bling_app_zero.ui.preview",
    "bling_app_zero.ui.preview.page",
    "bling_app_zero.ui.preview.align",
    "bling_app_zero.ui.preview.merge",
    "bling_app_zero.ui.preview.update",
    "bling_app_zero.ui.preview_final_estoque_inteligente",
    "bling_app_zero.ui.preview_final_bling",
    "bling_app_zero.ui.preview_final_bling_send",
    "bling_app_zero.core.instant_scraper",
    "bling_app_zero.core.instant_scraper.runner",
    "bling_app_zero.core.site_crawler",
    "bling_app_zero.services.bling.bling_sync",
]


REMOVED_LEGACY_IMPORTS = [
    "bling_app_zero.ui.origem_dados",
    "bling_app_zero.ui.origem_precificacao",
    "bling_app_zero.ui.origem_mapeamento",
    "bling_app_zero.ui.preview_final",
    "bling_app_zero.ui.hook_bus",
    "bling_app_zero.ui.hook_registry",
    "bling_app_zero.ui.plugins.estoque_final",
]


def check_imports(modules: Iterable[str] | None = None) -> ArchitectureCheckResult:
    checked: list[str] = []
    errors: list[str] = []

    for module_name in list(modules or CRITICAL_IMPORTS):
        module_name = str(module_name or "").strip()
        if not module_name:
            continue
        checked.append(module_name)
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")

    return ArchitectureCheckResult(ok=not errors, checked=checked, errors=errors)


def check_removed_legacy_absent() -> ArchitectureCheckResult:
    checked: list[str] = []
    errors: list[str] = []
    for module_name in REMOVED_LEGACY_IMPORTS:
        checked.append(module_name)
        try:
            importlib.import_module(module_name)
            errors.append(f"{module_name}: legado removido ainda importável")
        except ModuleNotFoundError:
            continue
        except Exception:
            continue
    return ArchitectureCheckResult(ok=not errors, checked=checked, errors=errors)


def assert_architecture_ok() -> None:
    result = check_imports()
    legacy = check_removed_legacy_absent()
    errors = result.errors + legacy.errors
    if not errors:
        return
    raise RuntimeError("Falha na arquitetura/imports críticos:\n" + "\n".join(errors))
