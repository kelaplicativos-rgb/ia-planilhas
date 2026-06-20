from pathlib import Path


def test_api_stock_flow_patch_is_activated() -> None:
    wizard_v2 = Path('bling_app_zero/ui/home_wizard_v2.py').read_text(encoding='utf-8')
    wrapper = Path('bling_app_zero/ui/home_wizard_api_stock_flow_patch.py').read_text(encoding='utf-8')
    patch_v2 = Path('bling_app_zero/ui/home_wizard_api_stock_flow_patch_v2.py').read_text(encoding='utf-8')
    pricing = Path('bling_app_zero/ui/home_wizard_pricing_step.py').read_text(encoding='utf-8')

    assert 'apply_api_stock_flow_patch(legacy)' in wizard_v2
    assert 'apply_api_stock_flow_patch_v2' in wrapper
    assert "home_router.VALID_SINGLE_PAGE_STEPS.add('operacao')" in wizard_v2
    assert "home_router.VALID_SINGLE_PAGE_STEPS.add(STEP_IA)" in wizard_v2

    assert 'STEP_PRECIFICACAO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD' in patch_v2
    assert 'api_stock_auto_base_ready' in patch_v2
    assert 'render_rules_center_step' in patch_v2
    assert 'wizard_footer_next_' in patch_v2
    assert 'render_ai_real_advanced_panel()' in patch_v2

    assert '_api_stock_pricing_optional' in pricing
    assert 'Precificação opcional para estoque via API' in pricing
