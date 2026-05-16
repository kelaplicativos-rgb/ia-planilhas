from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_universal_flow_modules_import() -> None:
    for module_name in [
        'bling_app_zero.ui.universal_flow',
        'bling_app_zero.ui.home_router',
    ]:
        importlib.import_module(module_name)


def test_home_router_keeps_universal_and_operational_flows() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "FLOW_UNIVERSAL = 'universal_model_flow'" in router
    assert "FLOW_WIZARD = 'wizard_cadastro_estoque'" in router
    assert "FLOW_PRICE_MULTISTORE = 'price_multistore_v2'" in router
    assert 'render_universal_flow' in router
    assert 'render_home_wizard' in router
    assert 'render_price_multistore_v2' in router
    assert 'Preencher qualquer modelo' in router
    assert 'Começar pelo modelo de destino' in router
    assert 'Fluxos operacionais mantidos' in router
    assert 'Começar cadastro' in router
    assert 'Começar estoque' in router
    assert 'Atualizar preços' in router
    assert 'busca por site, calculadora, mapeamento, preview e download final' in router
    assert 'Fluxo antigo extinto' not in router
    assert 'LEGACY_FLOWS' not in router
    assert 'legacy_flow_redirected_to_universal' not in router


def test_operational_flows_are_not_redirected_to_universal() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert 'safe_flow = FLOW_UNIVERSAL if flow in LEGACY_FLOWS else flow' not in router
    assert "st.session_state['home_slim_flow_operation'] = 'cadastro'" in router
    assert "st.session_state['home_slim_flow_operation'] = 'estoque'" in router
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


def test_universal_uploads_do_not_use_mobile_blocking_type_filters() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'SUPPORTED_UPLOAD_LABEL' in flow
    assert 'No celular, o seletor fica livre' in flow
    assert 'type=None' in flow
    assert "type=['xlsx'" not in flow
    assert "type=['xlsx', 'xls', 'csv'" not in flow
    assert 'Android bloqueie CSV/planilhas válidas' in flow


def test_universal_flow_state_is_signature_guarded() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'UNIVERSAL_SIGNATURE_KEY' in flow
    assert 'def _flow_signature(' in flow
    assert 'def _reset_universal_state_if_changed(' in flow
    assert "st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)" in flow
    assert "st.session_state.pop(UNIVERSAL_OUTPUT_KEY, None)" in flow
    assert "str(key).startswith('mapeiaai_universal_map_')" in flow


def test_universal_flow_uses_safe_widget_keys_and_openai_validated_suggester() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'suggest_mapping_with_openai' in flow
    assert "operation='universal'" in flow
    assert 'OpenAI validada' in flow
    assert 'def _mapping_widget_key(' in flow
    assert "mapeiaai_universal_map_{index}_" in flow
    assert "key=f'mapeiaai_universal_map_{target_name}'" not in flow


def test_universal_signature_changes_when_model_or_source_changes() -> None:
    flow_module = importlib.import_module('bling_app_zero.ui.universal_flow')

    model_a = pd.DataFrame(columns=['Nome', 'Preço'])
    model_b = pd.DataFrame(columns=['Nome', 'Preço', 'Estoque'])
    source_a = pd.DataFrame([{'Produto': 'A', 'Valor': '10'}])
    source_b = pd.DataFrame([{'Produto': 'B', 'Valor': '20'}])

    signature_a = flow_module._flow_signature(model_a, source_a)
    signature_model_changed = flow_module._flow_signature(model_b, source_a)
    signature_source_changed = flow_module._flow_signature(model_a, source_b)

    assert signature_a != signature_model_changed
    assert signature_a != signature_source_changed


def test_universal_output_still_keeps_exact_order_after_blindagem() -> None:
    from bling_app_zero.universal.output_builder import build_universal_output

    source = pd.DataFrame([{'Produto': 'Mouse', 'Valor': '29,90', 'Qtd': '3'}])
    model = pd.DataFrame(columns=['Preço destino', 'Nome destino', 'Sem origem'])
    mapping = {'Preço destino': 'Valor', 'Nome destino': 'Produto'}

    output = build_universal_output(source, model, mapping)

    assert list(output.columns) == ['Preço destino', 'Nome destino', 'Sem origem']
    assert output.iloc[0].to_dict() == {
        'Preço destino': '29,90',
        'Nome destino': 'Mouse',
        'Sem origem': '',
    }
