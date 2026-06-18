def test_blingfix_flow_order() -> None:
    from bling_app_zero.ui import home_wizard_constants as c
    from bling_app_zero.features_runtime import registry as r
    from bling_app_zero.core import wizard_engine as e

    assert c.UNIVERSAL_STEPS.index('regras') < c.UNIVERSAL_STEPS.index('ia')
    assert c.UNIVERSAL_STEPS.index('ia') < c.UNIVERSAL_STEPS.index('preview')
    assert r.UNIVERSAL_STEPS.index('regras') < r.UNIVERSAL_STEPS.index('ia')
    assert e.required_flag_for_step('ia') == 'has_rules'
