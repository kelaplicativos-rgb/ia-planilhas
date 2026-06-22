from __future__ import annotations

from pathlib import Path

from bling_app_zero.ui.shared_mapping import MAPPING_FIELDS_PER_PAGE


def test_mapping_limit_is_ten_fields_per_page() -> None:
    assert MAPPING_FIELDS_PER_PAGE == 10


def test_shared_mapping_has_pagination_and_scroll_to_top() -> None:
    content = Path('bling_app_zero/ui/shared_mapping.py').read_text(encoding='utf-8')

    assert 'MAPPING_FIELDS_PER_PAGE = 10' in content
    assert 'page_columns = target_columns[start:end]' in content
    assert '_render_mapping_page_controls(page_key, scroll_key, current_page, total_pages' in content
    assert 'scrollIntoView' in content
    assert 'st.rerun()' in content


def test_universal_flow_does_not_render_disabled_toggle_captions() -> None:
    content = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'Preço desligado: valores mantidos como vieram da origem.' not in content
    assert 'Mapeamento automático desligado. O mapeamento começará vazio para escolha manual.' not in content


def test_rules_panel_does_not_render_disabled_caption() -> None:
    content = Path('bling_app_zero/ui/shared_rules_resources.py').read_text(encoding='utf-8')

    assert 'Regras e recursos inteligentes desligados' not in content
