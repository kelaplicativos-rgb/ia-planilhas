from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOVED_FILES = [
    "origem_dados.py",
    "origem_precificacao.py",
    "origem_mapeamento.py",
    "preview_final.py",
    "hook_bus.py",
    "hook_registry.py",
]
REMOVED_IMPORTS = [
    "bling_app_zero.ui.origem_dados",
    "bling_app_zero.ui.origem_precificacao",
    "bling_app_zero.ui.origem_mapeamento",
    "bling_app_zero.ui.preview_final",
    "bling_app_zero.ui.hook_bus",
    "bling_app_zero.ui.hook_registry",
    "bling_app_zero.ui.plugins.estoque_final",
]
IGNORE_PARTS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


def _skip(path: Path) -> bool:
    return any(part in IGNORE_PARTS for part in path.parts)


def _scan_removed_files() -> list[str]:
    found: list[str] = []
    for path in ROOT.rglob("*.py"):
        if _skip(path):
            continue
        if path.name in REMOVED_FILES:
            found.append(str(path.relative_to(ROOT)))
    return found


def _scan_removed_imports() -> list[str]:
    found: list[str] = []
    for path in ROOT.rglob("*.py"):
        if _skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for bad in REMOVED_IMPORTS:
            if bad in text:
                found.append(f"{path.relative_to(ROOT)} -> {bad}")
    return found


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from bling_app_zero.healthcheck import run_healthcheck
    from bling_app_zero.utils.architecture_guard import assert_architecture_ok

    result = run_healthcheck()
    if not result.get("success"):
        print("ERRO: healthcheck falhou")
        print(result.get("errors"))
        return 1

    try:
        assert_architecture_ok()
    except Exception as exc:
        print("ERRO: architecture_guard falhou")
        print(exc)
        return 1

    found_removed = _scan_removed_files()
    if found_removed:
        print("ERRO: arquivos removidos ainda existem:")
        for item in found_removed:
            print(item)
        return 1

    found_imports = _scan_removed_imports()
    if found_imports:
        print("ERRO: imports removidos ainda aparecem no código:")
        for item in found_imports:
            print(item)
        return 1

    print("BLINGSCAN FINAL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
