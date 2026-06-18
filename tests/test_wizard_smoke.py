from bling_app_zero.ui import home_wizard_constants as c
from bling_app_zero.features_runtime import registry as r
from bling_app_zero.core import wizard_engine as e


def test_imports():
    import bling_app_zero.ui.home_wizard_v2
    import bling_app_zero.ui.rules_center_step
    import bling_app_zero.ui.ai_real_advanced_panel
    import bling_app_zero.core.flow_spine
    import bling_app_zero.core.wizard_state


def test_flow_order():
    assert c.UNIVERSAL_STEPS.index('regras') < c.UNIVERSAL_STEPS.index('ia')
    assert c.UNIVERSAL_STEPS.index('ia') < c.UNIVERSAL_STEPS.index('preview')
    assert r.UNIVERSAL_STEPS.index('regras') < r.UNIVERSAL_STEPS.index('ia')
    assert r.UNIVERSAL_STEPS.index('ia') < r.UNIVERSAL_STEPS.index('preview')
    assert e.required_flag_for_step('ia') == 'has_rules'


def test_flow_labels():
    assert c.STEP_LABELS['regras'] == 'Regras e Recursos Inteligentes'
    assert c.STEP_LABELS['ia'] == 'Inteligência Artificial'
