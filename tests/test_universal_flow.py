from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_universal_flow_modules_import() -> None:
    for module_name in [
        'bling_app_zero.ui.universal_flow',
        'bling_app_zero.ui.home_router',
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


def test_universal_flow_restores_full_system_steps() -> None:
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')

    assert 'Contrato final' in flow
    assert 'Origem dos dados' in flow
    assert 'Buscar produtos por site' in flow
    assert 'Anexar arquivo de origem' in flow
    assert 'run_site_pipeline' in flow
    assert 'Calculadora marketplace opcional' in flow
    assert 'Recursos IA Real' in flow
    assert 'Mapeamento manual com faróis' in flow
    assert 'Resumo dos faróis do mapeamento' in flow
    assert 'Preview final' in flow
    assert 'Planilha final' in flow
    assert 'Baixar planilha final mapeada' in flow
    assert 'Planilha final fiel ao contrato anexado' in flow
    assert 'Tipo detectado' not in flow
    assert 'detect_model_type' not in flow
    assert 'Modelo universal' not in flow
    assert 'build_universal_output' in flow
    assert 'validate_universal_output' in flow


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


def test_ai_text_rules_title_limit_and_prompt() -> None:
    from bling_app_zero.ai.ai_text_rules import MAX_TITLE_LENGTH, ai_text_rules_prompt, clean_title_to_limit

    title = clean_title_to_limit('Produto Gamer Ultra Resistente Com Cabo USB Reforçado Alta Performance Para Computador')

    assert MAX_TITLE_LENGTH == 59
    assert len(title) <= 59
    prompt = ai_text_rules_prompt()
    assert 'no máximo 59 caracteres' in prompt
    assert 'descrições complementares devem ser persuasivas' in prompt
    assert 'nunca altere preço, estoque, GTIN/EAN, SKU, ID, URL, imagem' in prompt
