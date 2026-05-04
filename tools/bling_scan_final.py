from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOVED = [
    "origem_dados.py",
    "origem_precificacao.py",
    "origem_mapeamento.py",
    "preview_final.py",
    "hook_bus.py",
    "hook_registry.py",
]


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

    found_removed = []
    for path in ROOT.rglob("*.py"):
        if path.name in REMOVED:
            found_removed.append(str(path.relative_to(ROOT)))
    if found_removed:
        print("ERRO: arquivos removidos ainda existem:")
        for item in found_removed:
            print(item)
        return 1

    print("BLINGSCAN FINAL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
