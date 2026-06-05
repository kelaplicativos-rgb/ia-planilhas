from __future__ import annotations

from pathlib import Path
from typing import Any

from bling_app_zero.core.system_inventory import (
    SYSTEM_INVENTORY,
    inventory_items,
    inventory_markdown as official_inventory_markdown,
    inventory_payload as official_inventory_payload,
    inventory_summary as official_inventory_summary,
    registered_paths,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/system_inventory_runtime.py'
IGNORED_DIR_NAMES = {
    '.git',
    '.github',
    '.idea',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '.streamlit',
    '.venv',
    '__pycache__',
    'node_modules',
    'venv',
}


def _project_root() -> Path:
    # .../bling_app_zero/core/system_inventory_runtime.py -> raiz do projeto
    return Path(__file__).resolve().parents[2]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _should_ignore(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def runtime_repository_python_files() -> tuple[str, ...]:
    """Varre os arquivos Python reais disponíveis no runtime do deploy.

    Diferente da varredura inicial do inventário oficial, esta cobre a raiz do
    repositório também. Assim `app.py` e qualquer novo `.py` criado pouco antes
    do diagnóstico aparecem no ZIP, mesmo quando ainda não foram cadastrados
    manualmente no inventário oficial.
    """
    root = _project_root()
    if not root.exists():
        return tuple()
    files: list[str] = []
    for path in root.rglob('*.py'):
        if _should_ignore(path):
            continue
        files.append(_relative_path(path, root))
    return tuple(sorted(set(files)))


def unregistered_repository_python_files() -> tuple[str, ...]:
    registered = registered_paths()
    files = runtime_repository_python_files()
    return tuple(path for path in files if path not in registered and not path.endswith('/__init__.py'))


def runtime_repository_snapshot() -> dict[str, Any]:
    files = runtime_repository_python_files()
    unregistered = unregistered_repository_python_files()
    return {
        'scope': 'repository_root_and_bling_app_zero',
        'python_files_total': len(files),
        'registered_paths_total': len(registered_paths()),
        'unregistered_files_total': len(unregistered),
        'unregistered_files': list(unregistered),
        'all_python_files': list(files),
        'responsible_file': RESPONSIBLE_FILE,
    }


def inventory_summary() -> dict[str, Any]:
    summary = dict(official_inventory_summary())
    snapshot = runtime_repository_snapshot()
    summary['runtime_repository_python_files_total'] = snapshot.get('python_files_total', 0)
    summary['runtime_repository_unregistered_files_total'] = snapshot.get('unregistered_files_total', 0)
    summary['runtime_repository_scan_scope'] = snapshot.get('scope')
    summary['runtime_repository_responsible_file'] = RESPONSIBLE_FILE
    return summary


def inventory_payload() -> dict[str, Any]:
    payload = dict(official_inventory_payload())
    repository_snapshot = runtime_repository_snapshot()
    payload['runtime_repository_file_snapshot'] = repository_snapshot
    payload['summary'] = inventory_summary()
    return payload


def inventory_markdown() -> str:
    base = official_inventory_markdown().rstrip()
    snapshot = runtime_repository_snapshot()
    lines = [base, '', '## Varredura automática ampliada do repositório', '']
    lines.append(f'- Escopo: `{snapshot.get("scope")}`')
    lines.append(f'- Arquivos Python detectados no repositório/runtime: {snapshot.get("python_files_total", 0)}')
    lines.append(f'- Arquivos cadastrados no inventário oficial: {snapshot.get("registered_paths_total", 0)}')
    lines.append(f'- Arquivos ainda não cadastrados diretamente: {snapshot.get("unregistered_files_total", 0)}')
    unregistered = list(snapshot.get('unregistered_files') or [])
    if unregistered:
        lines.append('')
        lines.append('### Arquivos Python não cadastrados diretamente na varredura ampliada')
        for path in unregistered[:500]:
            lines.append(f'- `{path}`')
    lines.append('')
    lines.append('### Observação')
    lines.append('Esta seção cobre também `app.py` e novos arquivos `.py` fora de `bling_app_zero`, desde que já estejam presentes no deploy/runtime no momento em que o diagnóstico for gerado.')
    return '\n'.join(lines).strip() + '\n'


__all__ = [
    'SYSTEM_INVENTORY',
    'inventory_items',
    'inventory_markdown',
    'inventory_payload',
    'inventory_summary',
    'runtime_repository_python_files',
    'runtime_repository_snapshot',
    'unregistered_repository_python_files',
]
