from __future__ import annotations

from pathlib import Path


def test_site_panel_state_uses_global_alert_instead_of_manual_html() -> None:
    source = Path('bling_app_zero/ui/site_panel_state.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.alerts import render_alert' in source
    assert "render_alert(str(message or ''), title='Atenção', variant='warning')" in source
    assert '<div style=' not in source
    assert 'unsafe_allow_html=True' not in source


def test_download_step_uses_flow_blocker_when_final_result_is_missing() -> None:
    source = Path('bling_app_zero/ui/cadastro_download_step.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Download bloqueado' in source
    assert 'O resultado final ainda não foi gerado' in source


def test_row_count_protection_uses_flow_blocker() -> None:
    source = Path('bling_app_zero/ui/cadastro_wizard_state.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Proteção ativada' in source
    assert 'perda silenciosa de produtos' in source
