from __future__ import annotations

from pathlib import Path


def _section(source: str, start: str, end: str) -> str:
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def test_universal_mapping_screen_does_not_build_final_file() -> None:
    source = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    mapping_section = _section(source, 'def _render_mapping_step', 'def _render_build_step')
    build_section = _section(source, 'def _render_build_step', 'def render_universal_flow')

    assert 'render_shared_contract_mapping' in mapping_section
    assert 'build_and_sync_mapping' in mapping_section
    assert 'render_shared_final_csv' not in mapping_section
    assert 'Confirmar mapeamento e ir para montagem' in mapping_section
    assert 'render_shared_final_csv' in build_section
    assert 'Montar planilha final agora' in build_section


def test_universal_flow_has_one_step_per_screen_keys() -> None:
    source = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert "UNIVERSAL_STEP_KEY = 'mapeiaai_universal_current_step'" in source
    assert "STEP_MODEL = 'modelo'" in source
    assert "STEP_SOURCE = 'origem'" in source
    assert "STEP_OPTIONS = 'opcionais'" in source
    assert "STEP_MAPPING = 'mapeamento'" in source
    assert "STEP_BUILD = 'montar'" in source
    assert 'A planilha final só é montada depois do mapeamento confirmado' in source
