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
    "bling_app_zero.ui.origem_dados",
    "bling_app_zero.ui.origem_site_panel",
    "bling_app_zero.ui.origem_precificacao",
    "bling_app_zero.ui.origem_mapeamento",
    "bling_app_zero.ui.preview_final",
    "bling_app_zero.ui.preview_final_bling",
    "bling_app_zero.ui.preview_final_bling_send",
    "bling_app_zero.core.instant_scraper",
    "bling_app_zero.core.instant_scraper.runner",
    "bling_app_zero.core.instant_scraper.autonomous_agent",
    "bling_app_zero.core.instant_scraper.auto_learning",
    "bling_app_zero.core.instant_scraper.self_healing",
    "bling_app_zero.core.site_crawler",
    "bling_app_zero.services.bling.bling_sync",
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


def assert_architecture_ok() -> None:
    result = check_imports()
    if result.ok:
        return
    raise RuntimeError("Falha na arquitetura/imports críticos:\n" + "\n".join(result.errors))
