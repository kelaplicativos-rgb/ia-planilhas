from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_universal_flow_modules_import() -> None:
    for module_name in [
        'bling_app_zero.ui.universal_flow',
        'bling_app_zero.ui.home_router',
        'bling_app_zero.ui.shared_calculator',
        'bling_app_zero.ui.shared_final_csv',
        'bling_app_zero.ui.shared_mapping',
        'bling_app_zero.ai.ai_text_rules',
    ]:
        importlib.import_module(module_name)


def test_home_router_uses_single_contract_screen_without_model_detection() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "FLOW_UNIVERSAL = 'universal_model_flow'" in router
    assert "FLOW_WIZARD" not in router
    assert "FLOW_PRICE_MULTISTORE" not in router
    assert 'render_universal_flow' in router
    assert 'render_home_wizard' not in router
    assert 'render_price_multistore_v2' not in router
    assert 'Anexe a planilha que vai ser mapeada' in router
    assert 'Planilha que vai ser mapeada' in router
    assert 'contrato fiel do download final' in router
    assert 'Continuar para origem dos dados' in router
    assert 'detect_model_type' not in router
    assert '_decision_for_model_type' not in router
    assert 'Tipo detectado' not in router
    assert 'Preencher qualquer modelo' not in router
    assert 'Começar cadastro' not in router
    assert 'Começar estoque' not in router
    assert 'Atualizar preços' not in router
    assert 'LEGACY_FLOWS' not in router


def test_home_contract_upload_goes_to_universal_flow_only() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "st.session_state['mapeiaai_universal_model_df'] = clean_df" in router
    assert "st.session_state['mapeiaai_final_contract_df'] = clean_df" in router
    assert "_set_flow(FLOW_UNIVERSAL)" in router
    assert 'home_model_contract_received' in router
    assert 'home_contract_model_uploaded' in router


def test_universal_flow_uses_shared_modules_for_core_steps() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'Contrato final' in flow
    assert 'Origem dos dados' in flow
    assert 'Buscar produtos por site' in flow
    assert 'Anexar arquivo de origem' in flow
    assert 'run_site_pipeline' in flow
    assert 'render_shared_calculator' in flow
    assert 'render_shared_contract_mapping' in flow
    assert 'render_shared_final_csv' in flow
    assert 'suggest_shared_mapping' in flow
    assert 'clear_shared_mapping_widgets' in flow
    assert 'Baixar planilha final mapeada' not in flow
    assert 'Mapeamento manual com faróis' not in flow
    assert 'Calculadora marketplace opcional' not in flow
    assert 'Preview final' not in flow
    assert 'Planilha final' not in flow
    assert 'Tipo detectado' not in flow
    assert 'detect_model_type' not in flow
    assert 'Modelo universal' not in flow


def test_shared_mapping_has_contract_farol_mapping() -> None:
    shared_mapping = Path('bling_app_zero/ui/shared_mapping.py').read_text(encoding='utf-8')

    assert 'render_shared_contract_mapping' in shared_mapping
    assert 'Mapeamento compartilhado com faróis' in shared_mapping
    assert 'Resumo dos faróis do mapeamento' in shared_mapping
    assert '🟢 alto' in shared_mapping
    assert '🟡 revisar' in shared_mapping
    assert '🔴 vazio' in shared_mapping
    assert 'suggest_mapping_with_openai' in shared_mapping


def test_shared_calculator_and_final_csv_exist() -> None:
    calculator = Path('bling_app_zero/ui/shared_calculator.py').read_text(encoding='utf-8')
    final_csv = Path('bling_app_zero/ui/shared_final_csv.py').read_text(encoding='utf-8')

    assert 'render_shared_calculator' in calculator
    assert 'Calculadora marketplace' in calculator
    assert 'apply_marketplace_calculation' in calculator
    assert 'render_shared_final_csv' in final_csv
    assert 'Preview final' in final_csv
    assert 'Planilha final' in final_csv
    assert 'Baixar planilha final mapeada' in final_csv
    assert 'build_shared_final_dataframe' in final_csv


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
    assert "clear_shared_mapping_widgets('mapeiaai_universal')" in flow


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


def test_ai_text_rules_title_limit_and_prompt() -> None:
    from bling_app_zero.ai.ai_text_rules import MAX_TITLE_LENGTH, ai_text_rules_prompt, clean_title_to_limit

    title = clean_title_to_limit('Produto Gamer Ultra Resistente Com Cabo USB Reforçado Alta Performance Para Computador')

    assert MAX_TITLE_LENGTH == 59
    assert len(title) <= 59
    prompt = ai_text_rules_prompt()
    assert 'no máximo 59 caracteres' in prompt
    assert 'descrições complementares devem ser persuasivas' in prompt
    assert 'nunca altere preço, estoque, GTIN/EAN, SKU, ID, URL, imagem' in prompt
