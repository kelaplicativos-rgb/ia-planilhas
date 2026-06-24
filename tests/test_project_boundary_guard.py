from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATHS = (
    ROOT / 'app.py',
    ROOT / 'bling_app_zero',
    ROOT / 'bling_backend',
    ROOT / '.streamlit',
    ROOT / 'render.yaml',
)
TEXT_FILE_SUFFIXES = {'.py', '.toml', '.yaml', '.yml', '.json', '.ini', '.cfg', '.html', '.css', '.js'}
SKIP_PARTS = {'.git', '.pytest_cache', '__pycache__', '.venv', 'venv', 'node_modules', 'browser_state'}


def _s(*codes: int) -> str:
    return ''.join(chr(code) for code in codes)


def _blocked_terms() -> tuple[str, ...]:
    return (
        _s(67, 97, 114, 111, 110, 97),
        _s(67, 97, 114, 111, 110, 97, 32, 65, 73),
        _s(67, 97, 114, 111, 110, 97, 115, 32, 73, 110, 116, 101, 108, 105, 103, 101, 110, 116, 101, 115),
        _s(66, 108, 97, 66, 108, 97, 67, 97, 114),
        _s(82, 111, 116, 97, 32, 67, 104, 101, 105, 97),
        _s(114, 111, 116, 97, 45, 99, 104, 101, 105, 97),
    )


def _should_scan(path: Path) -> bool:
    if not path.exists():
        return False
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    return path.suffix.lower() in TEXT_FILE_SUFFIXES


def _iter_app_text_files() -> list[Path]:
    files: list[Path] = []
    for base in APP_PATHS:
        if base.is_file() and _should_scan(base):
            files.append(base)
            continue
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if path.is_file() and _should_scan(path):
                files.append(path)
    return sorted(set(files))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-8', errors='ignore')


def test_app_boundary_contains_only_mapeiaai_bling_planilhas_context() -> None:
    blocked = tuple(term.lower() for term in _blocked_terms())
    violations: list[str] = []

    for path in _iter_app_text_files():
        text = _read_text(path).lower()
        found = [term for term in blocked if term in text]
        if found:
            relative = path.relative_to(ROOT).as_posix()
            violations.append(f'{relative}: {", ".join(found)}')

    assert not violations, 'Termo fora do escopo encontrado:\n' + '\n'.join(violations)


def test_streamlit_public_identity_remains_mapeiaai() -> None:
    config_path = ROOT / 'bling_app_zero' / 'core' / 'app_config.py'
    source = _read_text(config_path)

    assert "'page_title': 'MapeiaAI'" in source
    assert 'APP_VERSION =' in source
