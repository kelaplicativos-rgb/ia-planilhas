from __future__ import annotations

import importlib
from pathlib import Path


def test_universal_flow_modules_import() -> None:
    for module_name in [
        'bling_app_zero.ui.universal_flow',
        'bling_app_zero.ui.home_router',
    ]:
        importlib.import_module(module_name)


def test_home_router_exposes_universal_flow_as_primary_option() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "FLOW_UNIVERSAL = 'universal_model_flow'" in router
    assert 'render_universal_flow' in router
    assert 'Preencher qualquer modelo' in router
    assert 'Começar pelo modelo universal' in router
    assert 'Atalhos compatíveis' in router
    assert 'render_home_wizard()' in router
    assert 'render_price_multistore_v2()' in router


def test_universal_flow_preserves_final_model_contract() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'Modelo de destino' in flow
    assert 'Origem dos dados' in flow
    assert 'Mapeamento universal' in flow
    assert 'Planilha final idêntica ao modelo de destino em colunas e ordem.' in flow
    assert 'build_universal_output' in flow
    assert 'validate_universal_output' in flow
    assert 'Baixar planilha final universal' in flow
