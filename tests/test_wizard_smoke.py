from __future__ import annotations

import csv
import importlib
from io import StringIO
from pathlib import Path

import pandas as pd


LIGHT_CRITICAL_MODULES = [
    'app',
    'bling_app_zero.ui.home',
    'bling_app_zero.ui.home_router',
    'bling_app_zero.ui.home_wizard',
    'bling_app_zero.ui.home_wizard_state',
    'bling_app_zero.ui.home_wizard_scroll',
    'bling_app_zero.ui.home_wizard_review',
    'bling_app_zero.ui.home_autofluxo',
    'bling_app_zero.ui.home_models',
    'bling_app_zero.ui.home_shared',
    'bling_app_zero.ui.home_download',
    'bling_app_zero.ui.modelos_bling',
    'bling_app_zero.ui.modelos_bling_user_screen_min',
    'bling_app_zero.ui.cadastro_wizard_steps',
    'bling_app_zero.ui.cadastro_wizard_state',
    'bling_app_zero.ui.cadastro_entry_step',
    'bling_app_zero.ui.cadastro_mapping_step',
    'bling_app_zero.ui.cadastro_preview_step',
    'bling_app_zero.ui.cadastro_download_step',
    'bling_app_zero.ui.estoque_wizard_steps',
    'bling_app_zero.ui.estoque_wizard_state',
    'bling_app_zero.ui.estoque_entry_step',
    'bling_app_zero.ui.estoque_mapping_step',
    'bling_app_zero.ui.estoque_preview_step',
    'bling_app_zero.ui.estoque_download_step',
    'bling_app_zero.ui.shared_mapping',
    'bling_app_zero.ui.mapping_cadastro_flow',
    'bling_app_zero.ui.mapping_estoque_flow',
    'bling_app_zero.ui.mapping_field_widget',
    'bling_app_zero.ui.mapping_confirmation',
    'bling_app_zero.flows.site_as_source',
    'bling_app_zero.ui.wizard_state_guard',
    'bling_app_zero.ui.ai_sidebar',
    'bling_app_zero.ui.ai_analysis_panel',
    'bling_app_zero.ui.ai_mapping_apply_panel',
    'bling_app_zero.ai.ai_config',
    'bling_app_zero.ai.ai_client',
    'bling_app_zero.ai.ai_schema',
    'bling_app_zero.ai.ai_cache',
    'bling_app_zero.ai.ai_job_queue',
    'bling_app_zero.ai.ai_dataframe_tools',
    'bling_app_zero.ai.ai_column_reader',
    'bling_app_zero.ai.ai_header_matcher',
    'bling_app_zero.ai.ai_content_checker',
    'bling_app_zero.ai.ai_mapping_suggester',
    'bling_app_zero.ai.ai_quality_score',
    'bling_app_zero.ai.ai_orchestrator',
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.gtin',
]

EXPECTED_UNIVERSAL_STEPS = [
    'modelo',
    'origem',
    'entrada',
    'precificacao',
    'mapeamento',
    'regras',
    'preview',
    'download',
]


def test_light_critical_wizard_modules_import() -> None:
    for module_name in LIGHT_CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_site_critical_modules_import_without_running_scraper() -> None:
    for module_name in ['bling_app_zero.ui.site_panel', 'bling_app_zero.ui.site_outputs']:
        importlib.import_module(module_name)


def test_streamlit_entrypoint_uses_home_router() -> None:
    app_source = Path('app.py').read_text(encoding='utf-8')
    home_source = Path('bling_app_zero/ui/home.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.home import render_home' in app_source
    assert 'render_home()' in app_source
    assert 'render_home_router' in home_source or 'render_home_wizard' in home_source


def test_home_router_order_is_bling_then_universal_with_calculator_inside_flow() -> None:
    source = Path('bling_app_zero/ui/home_router.py').read_text(encoding='utf-8')

    assert "'Bling: Modelos Bling'" in source
    assert "'Modelos Universal'" in source
    assert "'Administração e links úteis'" in source
    assert "'Calculadora principal'" not in source
    assert "'home_order': 'bling_then_universal_then_internal_price_step'" in source
    assert 'A calculadora aparece somente na etapa Preço, dentro do fluxo.' in source
    assert source.index("'Bling: Modelos Bling'") < source.index("'Modelos Universal'")
    assert source.index("'Modelos Universal'") < source.index('_render_admin_links()')


def test_modelos_bling_screen_is_not_universal_screen() -> None:
    source = Path('bling_app_zero/ui/modelos_bling_user_screen_min.py').read_text(encoding='utf-8')

    assert '### Modelos Bling' in source
    assert 'Esta área é somente para modelos do Bling' in source
    assert 'Modelos Universal na Home' in source
    assert 'Modelo Bling cadastro' in source
    assert 'Modelo Bling estoque' in source
    assert 'Modelo Bling atualização de preços' in source


def test_universal_model_step_uses_bling_universal_destination_screen() -> None:
    wizard_source = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')
    models_source = Path('bling_app_zero/ui/home_models.py').read_text(encoding='utf-8')

    assert "_section_title(1, 'Modelos Universal')" in wizard_source
    assert 'render_home_bling_models()' in wizard_source
    assert 'def render_home_bling_models() -> None:' in models_source
    assert "st.markdown('#### Bling')" in models_source
    assert "st.markdown('##### Modelos Bling')" in models_source
    assert "st.markdown('##### Modelos Universal')" in models_source
    assert "st.markdown('#### Modelo de destino')" in models_source
    assert 'Esta etapa não faz parte da calculadora de preço.' in models_source
    assert 'Pode ser modelo Bling ou modelo universal com cabeçalho próprio.' in models_source


def test_wizard_step_order_matches_current_single_page_universal_flow() -> None:
    constants = importlib.import_module('bling_app_zero.ui.home_wizard_constants')

    assert constants.UNIVERSAL_STEPS == EXPECTED_UNIVERSAL_STEPS
    assert constants.CADASTRO_STEPS == EXPECTED_UNIVERSAL_STEPS
    assert constants.ESTOQUE_STEPS == EXPECTED_UNIVERSAL_STEPS
    assert constants.STEP_OPERACAO == 'operacao'
    assert constants.STEP_GERAR_ESTOQUE == 'gerar_estoque'
    assert constants.STEP_DOWNLOAD == 'download'
    assert constants.STEP_MAPEAMENTO == 'mapeamento'
    assert constants.STEP_REGRAS == 'regras'


def test_wizard_navigation_without_model_is_model_only(monkeypatch) -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    assert wizard.wizard_steps_for_operation('universal') == ['modelo']
    assert wizard.wizard_next_target('modelo', 'universal') == 'modelo'
    assert wizard.wizard_previous_target('modelo', 'universal') == 'modelo'


def test_wizard_navigation_with_model_is_linear_universal(monkeypatch) -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {'home_modelo_cadastro_df': pd.DataFrame(columns=['Descricao'])}, raising=False)

    steps = wizard.wizard_steps_for_operation('universal')
    assert steps == EXPECTED_UNIVERSAL_STEPS
    for index, step in enumerate(steps):
        assert wizard.wizard_previous_target(step, 'universal') == steps[max(0, index - 1)]
        assert wizard.wizard_next_target(step, 'universal') == steps[min(len(steps) - 1, index + 1)]
    assert wizard.wizard_next_target('operacao', 'universal') == 'entrada'


def test_home_models_syncs_any_destination_model_as_universal(monkeypatch) -> None:
    home_models = importlib.import_module('bling_app_zero.ui.home_models')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    df = pd.DataFrame(columns=['Descricao', 'Preco'])
    home_models.save_home_models(df, None, replace_missing=True)

    assert st.session_state['home_slim_flow_operation'] == 'universal'
    assert st.session_state['operacao_final'] == 'universal'
    assert st.session_state['tipo_operacao_final'] == 'universal'
    assert st.session_state['home_detected_operation'] == 'universal'
    assert home_models.has_home_models() is True


def test_mapping_step_exposes_quick_download_before_ai_review() -> None:
    mapping_source = Path('bling_app_zero/ui/cadastro_mapping_step.py').read_text(encoding='utf-8')
    wizard_source = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')

    assert 'Download imediato' in mapping_source
    assert 'cadastro_mapping_ready' in mapping_source
    assert "download_final(df_final, 'universal', 'atalho_pos_mapeamento_universal')" in mapping_source
    assert 'Revisão final / IA Real' in mapping_source
    assert 'render_universal_mapeamento_step()' in wizard_source
    assert '_render_ai_review_step' in wizard_source
    assert wizard_source.index('render_universal_mapeamento_step()') < wizard_source.index('_render_ai_review_step')


def test_ai_sidebar_byok_without_secrets_fallback() -> None:
    ai_config = Path('bling_app_zero/ai/ai_config.py').read_text(encoding='utf-8')
    ai_client = Path('bling_app_zero/ai/ai_client.py').read_text(encoding='utf-8')
    ai_sidebar = Path('bling_app_zero/ui/ai_sidebar.py').read_text(encoding='utf-8')
    sidebar_tools = Path('bling_app_zero/ui/sidebar_tools.py').read_text(encoding='utf-8')

    assert 'AI_USER_API_KEY' in ai_config
    assert 'st.secrets' not in ai_config
    assert 'st.secrets' not in ai_client
    assert 'OPENAI_RESPONSES_URL' in ai_client
    assert "type='password'" in ai_sidebar
    assert 'O sistema não usa chave em Secrets como fallback.' in ai_sidebar
    assert 'IA do Mapeia.AI' in sidebar_tools
    assert '_render_ai_sidebar_lazy' in sidebar_tools


def test_ai_local_modules_suggest_mapping_and_quality() -> None:
    from bling_app_zero.ai.ai_orchestrator import analyze_mapping, analyze_origin

    source = pd.DataFrame(
        [
            {
                'Produto': 'Cabo USB Tipo C',
                'Valor Venda': '19,90',
                'Saldo': '8',
                'Codigo de barras': '7891234567895',
            }
        ]
    )
    target = pd.DataFrame(columns=['Descricao', 'Preco unitario', 'Estoque', 'GTIN/EAN'])

    origin_result = analyze_origin(source)
    mapping_result = analyze_mapping(source, target)

    assert origin_result.ok is True
    assert mapping_result.ok is True
    assert origin_result.data['quality']['score'] >= 70
    suggestions = mapping_result.data['mapping']['suggestions']
    assert any(item['target_column'] == 'Preco unitario' and item['source_column'] == 'Valor Venda' for item in suggestions)
    assert any(item['target_column'] == 'Estoque' and item['source_column'] == 'Saldo' for item in suggestions)


def test_ai_analysis_panel_is_informational_only() -> None:
    panel = Path('bling_app_zero/ui/ai_analysis_panel.py').read_text(encoding='utf-8')
    cadastro_entry = Path('bling_app_zero/ui/cadastro_entry_step.py').read_text(encoding='utf-8')
    estoque_entry = Path('bling_app_zero/ui/estoque_entry_step.py').read_text(encoding='utf-8')

    assert 'render_ai_origin_analysis_panel' in cadastro_entry
    assert 'render_ai_origin_analysis_panel' in estoque_entry
    assert 'Nenhuma alteração automática será aplicada.' in panel
    assert 'não altera a planilha' in panel
    assert 'não aplica mapeamento' in panel
    assert "st.session_state['mapping_cadastro']" not in panel
    assert 'st.session_state["mapping_cadastro"]' not in panel
    assert "st.session_state['mapping_estoque']" not in panel
    assert 'st.session_state["mapping_estoque"]' not in panel


def test_ai_mapping_apply_panel_is_safe_and_manual() -> None:
    panel = Path('bling_app_zero/ui/ai_mapping_apply_panel.py').read_text(encoding='utf-8')
    cadastro_flow = Path('bling_app_zero/ui/mapping_cadastro_flow.py').read_text(encoding='utf-8')
    estoque_flow = Path('bling_app_zero/ui/mapping_estoque_flow.py').read_text(encoding='utf-8')

    assert 'MIN_CONFIDENCE_TO_APPLY = 0.85' in panel
    assert 'só preenche campos vazios/sem escolha' in panel
    assert 'nunca sobrescreve mapeamento já escolhido pelo usuário' in panel
    assert 'Nada será confirmado automaticamente.' in panel
    assert "st.session_state.pop('cadastro_mapping_confirmed', None)" in panel
    assert 'render_ai_mapping_apply_panel' in cadastro_flow
    assert 'render_ai_mapping_apply_panel' in estoque_flow
    assert "operation='cadastro'" in cadastro_flow
    assert "operation='estoque'" in estoque_flow


def test_cadastro_mapping_ready_requires_manual_confirmation(monkeypatch) -> None:
    steps = importlib.import_module('bling_app_zero.ui.cadastro_wizard_steps')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    st.session_state['df_final_cadastro'] = pd.DataFrame([{'Descricao': 'Produto teste'}])
    st.session_state['mapping_cadastro'] = {'Descricao': 'Nome'}

    assert steps.cadastro_mapping_ready() is False

    st.session_state['cadastro_mapping_confirmed'] = True
    assert steps.cadastro_mapping_ready() is True


def test_download_final_uses_template_exporter_for_attached_model() -> None:
    home_shared = Path('bling_app_zero/ui/home_shared.py').read_text(encoding='utf-8')
    home_download = Path('bling_app_zero/ui/home_download.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.home_download import (' in home_shared
    assert 'download_final' in home_shared
    assert 'df_signature' in home_shared
    assert 'from bling_app_zero.core.template_download_exporter import (' in home_download
    assert 'build_template_download_bytes' in home_download
    assert 'can_export_from_template' in home_download
    assert 'output_name_for_template' in home_download
    assert 'mime_for_template_output' in home_download
    assert 'build_template_download(download_df.copy())' in home_download
    assert '.to_csv(' not in home_shared
    assert '.to_csv(' not in home_download


def test_gtin_invalid_values_are_cleaned() -> None:
    from bling_app_zero.core.gtin import clean_gtin

    assert clean_gtin('123') == ''
    assert clean_gtin('0000000000000') == ''
    assert clean_gtin('abc789') == ''


def test_exporter_uses_bling_csv_contract() -> None:
    from bling_app_zero.core.exporter import to_bling_csv_bytes

    df = pd.DataFrame(
        [
            {
                'Descricao': 'Produto teste',
                'GTIN/EAN': '123',
                'URL imagens externas': 'https://a.com/1.jpg, https://a.com/2.jpg',
            }
        ]
    )
    csv_bytes = to_bling_csv_bytes(df)
    text = csv_bytes.decode('utf-8-sig')
    rows = list(csv.reader(StringIO(text), delimiter=';'))

    assert len(rows) == 2
    header = rows[0]
    values = rows[1]
    row = dict(zip(header, values))

    assert header == ['Descricao', 'GTIN/EAN', 'URL imagens externas']
    assert row['GTIN/EAN'] == ''
    assert row['URL imagens externas'] == 'https://a.com/1.jpg|https://a.com/2.jpg'


def test_exporter_removes_columns_outside_explicit_contract() -> None:
    from bling_app_zero.core.exporter import to_bling_csv_bytes

    df = pd.DataFrame(
        [
            {
                'Codigo': 'P001',
                'Descricao': 'Produto teste',
                'Preco unitario (OBRIGATORIO)': '10',
                'Coluna fora do Bling': 'nao deve exportar',
            }
        ]
    )
    contract = ['Codigo', 'Descricao', 'Preco unitario (OBRIGATORIO)', 'GTIN/EAN']
    csv_bytes = to_bling_csv_bytes(df, operation='cadastro', contract_columns=contract)
    text = csv_bytes.decode('utf-8-sig')
    rows = list(csv.reader(StringIO(text), delimiter=';'))

    assert rows[0] == contract
    assert len(rows[1]) == len(contract)
    assert 'Coluna fora do Bling' not in rows[0]
    assert dict(zip(rows[0], rows[1]))['GTIN/EAN'] == ''
