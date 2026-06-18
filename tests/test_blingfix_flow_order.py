def test_blingfix_flow_order() -> None:
    from bling_app_zero.ui import home_wizard_constants as c
    from bling_app_zero.features_runtime import registry as r
    from bling_app_zero.core import wizard_engine as e
    from bling_app_zero.core import wizard_state as s

    expected = [
        'modelo',
        'origem',
        'entrada',
        'precificacao',
        'categorizacao',
        'mapeamento',
        'regras',
        'ia',
        'preview',
        'download',
    ]

    assert c.UNIVERSAL_STEPS == expected
    assert list(r.UNIVERSAL_STEPS) == expected
    assert list(s.WIZARD_STEPS) == expected
    assert c.UNIVERSAL_STEPS.index('regras') < c.UNIVERSAL_STEPS.index('ia')
    assert c.UNIVERSAL_STEPS.index('ia') < c.UNIVERSAL_STEPS.index('preview')
    assert r.UNIVERSAL_STEPS.index('regras') < r.UNIVERSAL_STEPS.index('ia')
    assert s.WIZARD_STEPS.index('regras') < s.WIZARD_STEPS.index('ia')
    assert e.required_flag_for_step('categorizacao') == 'has_pricing'
    assert e.required_flag_for_step('ia') == 'has_rules'
