from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve().relative_to(ROOT).as_posix()

TEXT_FILE_SUFFIXES = {
    '.py', '.md', '.txt', '.toml', '.yaml', '.yml', '.json', '.sql', '.ini', '.cfg', '.html', '.css', '.js'
}
SKIP_PARTS = {'.git', '.pytest_cache', '__pycache__', '.venv', 'venv', 'node_modules', '.streamlit/browser_state'}


def _s(*codes: int) -> str:
    return ''.join(chr(code) for code in codes)


def _blocked_terms() -> tuple[str, ...]:
    # Built from character codes so this guard does not match itself.
    return (
        _s(67, 97, 114, 111, 110, 97),
        _s(67, 97, 114, 111, 110, 97, 32, 65, 73),
        _s(67, 97, 114, 111, 110, 97, 115, 32, 73, 110, 116, 101, 108, 105, 103, 101, 110, 116, 101, 115),
        _s(66, 108, 97, 66, 108, 97, 67, 97, 114),
        _s(82, 111, 116, 97, 32, 67, 104, 101, 105, 97),
        _s(114, 111, 116, 97, 45, 99, 104, 101, 105, 97),
    )


def _iter_project_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative == THIS_FILE:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-8', errors='ignore')


def test_project_boundary_contains_only_mapeiaai_bling_planilhas_context() -> None:
    blocked = tuple(term.lower() for term in _blocked_terms())
    violations: list[str] = []

    for path in _iter_project_text_files():
        text = _read_text(path).lower()
        found = [term for term in blocked if term in text]
        if found:
            relative = path.relative_to(ROOT).as_posix()
            violations.append(f'{relative}: {", ".join(found)}')

    assert not violations, 'Referência de projeto externo encontrada:\n' + '\n'.join(violations)


def test_streamlit_public_identity_remains_mapeiaai() -> None:
    config_path = ROOT / 'bling_app_zero' / 'core' / 'app_config.py'
    source = _read_text(config_path)

    assert "'page_title': 'MapeiaAI'" in source
    assert 'APP_VERSION =' in source
