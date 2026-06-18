from pathlib import Path


def test_blingfix_rules_ai_split_marker() -> None:
    wizard_v2 = Path('bling_app_zero/ui/home_wizard_v2.py').read_text(encoding='utf-8')
    rules_step = Path('bling_app_zero/ui/rules_center_step.py').read_text(encoding='utf-8')

    assert "STEP_IA = 'ia'" in wizard_v2
    assert 'def _render_rules_resources_step' in wizard_v2
    assert 'def _render_ai_step' in wizard_v2
    assert wizard_v2.index('def _render_rules_resources_step') < wizard_v2.index('def _render_ai_step')
    assert 'render_ai_real_advanced_panel' not in rules_step
