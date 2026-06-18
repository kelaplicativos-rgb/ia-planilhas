from bling_app_zero.ui import home_wizard_constants as c
from bling_app_zero.features_runtime import registry as r
from bling_app_zero.core import wizard_engine as e
from bling_app_zero.core import wizard_state as s


EXPECTED_UNIVERSAL_STEPS = [
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


def test_flow_order():
    assert c.UNIVERSAL_STEPS == EXPECTED_UNIVERSAL_STEPS
    assert list(r.UNIVERSAL_STEPS) == EXPECTED_UNIVERSAL_STEPS
    assert list(s.WIZARD_STEPS) == EXPECTED_UNIVERSAL_STEPS
    assert c.UNIVERSAL_STEPS.index('categorizacao') < c.UNIVERSAL_STEPS.index('mapeamento')
    assert c.UNIVERSAL_STEPS.index('regras') < c.UNIVERSAL_STEPS.index('ia')
    assert c.UNIVERSAL_STEPS.index('ia') < c.UNIVERSAL_STEPS.index('preview')
    assert r.UNIVERSAL_STEPS.index('regras') < r.UNIVERSAL_STEPS.index('ia')
    assert r.UNIVERSAL_STEPS.index('ia') < r.UNIVERSAL_STEPS.index('preview')
    assert s.WIZARD_STEPS.index('regras') < s.WIZARD_STEPS.index('ia')
    assert s.WIZARD_STEPS.index('ia') < s.WIZARD_STEPS.index('preview')
    assert e.required_flag_for_step('categorizacao') == 'has_data'
    assert e.required_flag_for_step('mapeamento') == 'has_pricing'
    assert e.required_flag_for_step('ia') == 'has_rules'


def test_flow_labels():
    assert c.STEP_LABELS['regras'] == 'Regras e Recursos Inteligentes'
    assert c.STEP_LABELS['ia'] == 'Inteligência Artificial'


def test_wizard_state_defaults_to_first_official_step():
    wizard = s.WizardState()
    assert wizard.step == 'modelo'
    assert wizard.steps[0] == 'modelo'


def test_categorization_can_open_with_data_without_pricing():
    wizard = s.WizardState(has_model=True, has_origin=True, has_data=True, has_pricing=False)
    allowed, warning = e.can_enter_step(wizard, 'categorizacao')
    assert allowed is True
    assert warning == ''
