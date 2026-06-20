from pathlib import Path


def test_api_stock_flow_patch_is_activated() -> None:
    wizard_v2 = Path('bling_app_zero/ui/home_wizard_v2.py').read_text(encoding='utf-8')
    patch = Path('bling_app_zero/ui/home_wizard_api_stock_flow_patch.py').read_text(encoding='utf-8')

    assert 'apply_api_stock_flow_patch(legacy)' in wizard_v2
    assert "home_router.VALID_SINGLE_PAGE_STEPS.add('operacao')" in wizard_v2
    assert "home_router.VALID_SINGLE_PAGE_STEPS.add(STEP_IA)" in wizard_v2

    assert 'op == OP_ESTOQUE and _api_direct_flow()' in patch
    assert 'steps += [STEP_PRECIFICACAO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]' in patch
    assert 'legacy._nav = _render_progress_only' in patch
    assert 'legacy._render_step = _render_step' in patch
    assert 'wizard_footer_next_' in patch
    assert 'render_ai_real_advanced_panel()' in patch
