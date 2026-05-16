from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_home_router_keeps_only_first_screen_changed_and_returns_to_wizard() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert 'Anexe a planilha que vai ser mapeada' in router
    assert 'Planilha que vai ser mapeada' in router
    assert 'render_home_wizard' in router
    assert 'render_universal_flow' not in router
    assert "FLOW_WIZARD = 'wizard_cadastro_estoque'" in router
    assert "_set_flow(FLOW_WIZARD)" in router
    assert 'buscar produtos por site, anexar origem, calculadora, mapeamento, preview e download final' in router
    assert 'detect_model_type' not in router
    assert 'Tipo detectado' not in router


def test_home_contract_is_shared_with_old_wizard_model_keys() -> None:
    router = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "st.session_state['home_modelo_cadastro_df'] = clean_df.copy()" in router
    assert "st.session_state['df_modelo_cadastro'] = clean_df.copy()" in router
    assert "st.session_state['modelo_cadastro_df'] = clean_df.copy()" in router
    assert "st.session_state['home_modelo_estoque_df'] = clean_df.copy()" in router
    assert "st.session_state['df_modelo_estoque'] = clean_df.copy()" in router
    assert "st.session_state['modelo_estoque_df'] = clean_df.copy()" in router
    assert "st.session_state.setdefault('home_slim_flow_operation', 'cadastro')" in router


def test_bling_links_panel_is_used_on_download_steps() -> None:
    panel = Path('bling_app_zero/ui/bling_links_panel.py').read_text(encoding='utf-8')
    cadastro = Path('bling_app_zero/ui/cadastro_download_step.py').read_text(encoding='utf-8')
    estoque = Path('bling_app_zero/ui/estoque_download_step.py').read_text(encoding='utf-8')

    assert 'render_bling_links_panel' in panel
    assert 'BLING_IMPORTADOR_PRODUTOS_URL' in panel
    assert 'BLING_IMPORTADOR_ESTOQUE_URL' in panel
    assert 'render_bling_links_panel()' in cadastro
    assert 'render_bling_links_panel()' in estoque


def test_universal_flow_modules_still_import_but_are_not_home_router_path() -> None:
    for module_name in [
        'bling_app_zero.ui.home_router',
        'bling_app_zero.ui.home_wizard',
        'bling_app_zero.ui.universal_flow',
        'bling_app_zero.ai.ai_text_rules',
    ]:
        importlib.import_module(module_name)


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
