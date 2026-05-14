from __future__ import annotations

import csv
import importlib
from io import StringIO
from pathlib import Path

import pandas as pd


LIGHT_CRITICAL_MODULES = [
    'app',
    'bling_app_zero.ui.home',
    'bling_app_zero.ui.home_wizard',
    'bling_app_zero.ui.rules_center_step',
    'bling_app_zero.ui.rules_panel',
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
    'bling_app_zero.ui.mapping_pagination',
    'bling_app_zero.ui.mapping_filters',
    'bling_app_zero.ui.mapping_field_widget',
    'bling_app_zero.ui.mapping_preview_builder',
    'bling_app_zero.ui.mapping_confirmation',
    'bling_app_zero.ui.mapping_sidebar_rule_badge',
    'bling_app_zero.core.sidebar_rule_targets',
    'bling_app_zero.flows.site_as_source',
    'bling_app_zero.ui.wizard_state_guard',
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.gtin',
]

SITE_CRITICAL_MODULES = [
    'bling_app_zero.ui.site_panel',
    'bling_app_zero.ui.site_outputs',
]

EXPECTED_CADASTRO_STEPS = [
    'modelo',
    'operacao',
    'precificacao',
    'origem',
    'regras',
    'entrada',
    'mapeamento',
    'preview',
    'download',
]

EXPECTED_ESTOQUE_STEPS = [
    'modelo',
    'operacao',
    'precificacao',
    'origem',
    'regras',
    'entrada',
    'gerar_estoque',
    'preview',
    'download',
]


def test_light_critical_wizard_modules_import() -> None:
    for module_name in LIGHT_CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_site_critical_modules_import_without_running_scraper() -> None:
    for module_name in SITE_CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_streamlit_entrypoint_uses_home_wizard() -> None:
    app_source = Path('app.py').read_text(encoding='utf-8')
    home_source = Path('bling_app_zero/ui/home.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.home import render_home' in app_source
    assert 'render_home()' in app_source
    assert 'from bling_app_zero.ui.home_wizard import render_home_wizard' in home_source
    assert 'from bling_app_zero.ui.wizard_state_guard import run_wizard_state_guard' in home_source
    assert 'run_wizard_state_guard()' in home_source
    assert 'render_home_wizard()' in home_source


def test_wizard_step_order_is_preserved() -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')

    assert wizard.CADASTRO_STEPS == EXPECTED_CADASTRO_STEPS
    assert wizard.ESTOQUE_STEPS == EXPECTED_ESTOQUE_STEPS
    assert wizard.STEP_DOWNLOAD == 'download'
    assert wizard.STEP_GERAR_ESTOQUE == 'gerar_estoque'
    assert wizard.STEP_MAPEAMENTO == 'mapeamento'
    assert wizard.STEP_REGRAS == 'regras'


def test_fixed_navigation_is_single_source_for_wizard_next_back() -> None:
    wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')

    assert 'TOP_NAV_RENDERED_KEY' in wizard
    assert "data-testid=\"wizard-fixed-navigation\"" in wizard
    assert "st.button('← Voltar'" in wizard
    assert "st.button(next_label" in wizard
    assert 'def _render_top_navigation() -> None:' in wizard
    assert '_render_top_navigation()' in wizard
    assert "if bool(st.session_state.get(TOP_NAV_RENDERED_KEY))" in wizard
    assert "_render_nav_buttons(allow_next=" not in wizard
    assert "wizard_download_back" not in wizard
    assert "wizard_estoque_download_back" not in wizard
    assert "← Voltar para preview" not in wizard
    assert "_render_reset_only_footer" in wizard


def test_origin_step_does_not_auto_advance_after_selection() -> None:
    wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')
    origin_block = wizard.split('def _render_origin_step() -> None:', 1)[1].split('def _render_rules_step() -> None:', 1)[0]

    assert '_sync_flow_state(origin, operation)' in origin_block
    assert '_go_to_step(STEP_ENTRADA' not in origin_block
    assert 'origin_selected_auto_next' not in origin_block
    assert 'Use Avançar para continuar ou Voltar para revisar sem perder os dados.' in origin_block


def test_rules_center_is_plugged_into_fixed_wizard_navigation() -> None:
    constants = Path('bling_app_zero/ui/home_wizard_constants.py').read_text(encoding='utf-8')
    wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')
    rules_step = Path('bling_app_zero/ui/rules_center_step.py').read_text(encoding='utf-8')

    assert "STEP_REGRAS = 'regras'" in constants
    assert 'STEP_REGRAS,' in constants
    assert "STEP_REGRAS: 'Regras'" in constants
    assert 'from bling_app_zero.ui.rules_center_step import render_rules_center_step, rules_center_ready' in wizard
    assert 'elif step == STEP_REGRAS:' in wizard
    assert 'render_rules_center_step()' in wizard
    assert 'if step == STEP_REGRAS:' in wizard
    assert 'return rules_center_ready()' in wizard
    assert 'Regra principal: mapeamento/manual ganha' in rules_step


def test_mapping_stays_paginated_for_mobile_performance() -> None:
    pagination_source = Path('bling_app_zero/ui/mapping_pagination.py').read_text(encoding='utf-8')
    field_widget_source = Path('bling_app_zero/ui/mapping_field_widget.py').read_text(encoding='utf-8')
    filters_source = Path('bling_app_zero/ui/mapping_filters.py').read_text(encoding='utf-8')

    assert 'def visible_targets(' in pagination_source
    assert 'MOBILE_MAPPING_PAGE_SIZE = 6' in pagination_source
    assert "label = f'Campos {start + 1} a {end} de {total_targets}" in pagination_source
    assert "st.button('← Campos anteriores'" in pagination_source
    assert "st.button('Próximos campos →'" in pagination_source
    assert 'st.selectbox(' in field_widget_source
    assert '🟣 Regras/recursos' in filters_source


def test_sidebar_rules_panel_is_read_only_summary() -> None:
    rules_panel = Path('bling_app_zero/ui/rules_panel.py').read_text(encoding='utf-8')

    assert 'Resumo somente leitura' in rules_panel
    assert 'Abrir Central de Regras' in rules_panel
    assert 'render_resources_tab' not in rules_panel
    assert 'add_custom_rule' not in rules_panel
    assert 'update_custom_rule_by_id' not in rules_panel
    assert 'remove_custom_rule_by_id' not in rules_panel
    assert 'set_custom_rule_enabled' not in rules_panel
    assert 'st.text_input(' not in rules_panel
    assert 'st.toggle(' not in rules_panel


def test_home_wizard_reset_clears_mapping_and_outputs() -> None:
    home_wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')
    constants = Path('bling_app_zero/ui/home_wizard_constants.py').read_text(encoding='utf-8')

    assert 'def _reset_outputs_for_operation_change() -> None:' in home_wizard
    assert "'rules_center_reviewed'" in constants
    assert "'cadastro_mapping_confirmed'" in constants
    assert "'cadastro_mapping_confirmed_signature'" in constants
    assert "'df_final_cadastro'" in constants
    assert "'mapping_cadastro'" in constants
    assert "'mapping_confidence_cadastro'" in constants
    assert "'estoque_multi_outputs'" in constants
    assert "'df_final_estoque'" in constants
    assert "'mapping_estoque'" in constants


def test_wizard_state_guard_tracks_cross_operation_keys() -> None:
    guard = importlib.import_module('bling_app_zero.ui.wizard_state_guard')

    assert guard.SITE_RAW_BY_OPERATION['cadastro'] == 'df_site_bruto_cadastro'
    assert guard.SITE_RAW_BY_OPERATION['estoque'] == 'df_site_bruto_estoque'
    assert guard.SITE_INTERNAL_BY_OPERATION['cadastro'] == 'df_origem_site_como_planilha_cadastro'
    assert guard.SITE_INTERNAL_BY_OPERATION['estoque'] == 'df_origem_site_como_planilha_estoque'

    cadastro_keys = set(guard.SITE_OUTPUT_KEYS_BY_OPERATION['cadastro'])
    estoque_keys = set(guard.SITE_OUTPUT_KEYS_BY_OPERATION['estoque'])

    assert 'df_final_cadastro' in cadastro_keys
    assert 'mapping_cadastro' in cadastro_keys
    assert 'mapping_confidence_cadastro' in cadastro_keys
    assert 'cadastro_mapping_confirmed' in cadastro_keys
    assert 'cadastro_mapping_confirmed_signature' in cadastro_keys
    assert 'estoque_multi_outputs' in estoque_keys
    assert 'df_final_estoque' in estoque_keys
    assert 'mapping_estoque' in estoque_keys


def test_shared_mapping_uses_modular_flows() -> None:
    shared_mapping = Path('bling_app_zero/ui/shared_mapping.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.mapping_cadastro_flow import render_manual_mapping' in shared_mapping
    assert 'from bling_app_zero.ui.mapping_estoque_flow import render_manual_stock_mapping' in shared_mapping
    assert 'from bling_app_zero.ui.cadastro_mapping import' not in shared_mapping


def test_project_no_longer_imports_legacy_cadastro_mapping() -> None:
    forbidden = 'from bling_app_zero.ui.cadastro_mapping import'
    for path in Path('bling_app_zero').rglob('*.py'):
        if path.as_posix() == 'bling_app_zero/ui/cadastro_mapping.py':
            continue
        assert forbidden not in path.read_text(encoding='utf-8')


def test_file_origin_does_not_reuse_old_site_origin() -> None:
    cadastro_entry = Path('bling_app_zero/ui/cadastro_entry_step.py').read_text(encoding='utf-8')
    estoque_entry = Path('bling_app_zero/ui/estoque_entry_step.py').read_text(encoding='utf-8')

    assert "df_origem_site = get_site_source_for_operation('cadastro') if site_origin else None" in cadastro_entry
    assert 'upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)' in cadastro_entry
    assert 'df_origem_site = get_estoque_site_source() if site_origin else None' in estoque_entry
    assert 'upload = empty_estoque_upload_result() if site_origin else render_estoque_upload(model_loaded)' in estoque_entry


def test_site_origin_uses_empty_upload_result() -> None:
    cadastro_entry = Path('bling_app_zero/ui/cadastro_entry_step.py').read_text(encoding='utf-8')
    estoque_entry = Path('bling_app_zero/ui/estoque_entry_step.py').read_text(encoding='utf-8')

    assert 'def empty_cadastro_upload_result() -> SmartUploadResult:' in cadastro_entry
    assert 'def empty_estoque_upload_result() -> SmartUploadResult:' in estoque_entry
    assert 'upload = empty_cadastro_upload_result() if site_origin else render_cadastro_source_upload(None)' in cadastro_entry
    assert 'upload = empty_estoque_upload_result() if site_origin else render_estoque_upload(model_loaded)' in estoque_entry
    assert 'source_file=None' in cadastro_entry
    assert 'source_file=None' in estoque_entry


def test_site_origin_is_stored_by_operation() -> None:
    site_panel = Path('bling_app_zero/ui/site_panel.py').read_text(encoding='utf-8')
    site_as_source = Path('bling_app_zero/flows/site_as_source.py').read_text(encoding='utf-8')

    assert "return f'df_site_bruto_{operation}'" in site_panel
    assert "st.session_state[_site_df_key(operation)] = df_site" in site_panel
    assert "other = 'estoque' if operation == 'cadastro' else 'cadastro'" in site_panel
    assert "st.session_state.pop(_site_df_key(other), None)" in site_panel
    assert "return f'{SITE_SOURCE_KEY}_{_op_key(operation)}'" in site_as_source
    assert "return f'{SITE_RAW_LEGACY_KEY}_{_op_key(operation)}'" in site_as_source
    assert "st.session_state[_raw_source_key(normalized)]" in site_as_source
    assert "st.session_state.pop(_raw_source_key(other), None)" in site_as_source


def test_cadastro_mapping_ready_requires_manual_confirmation(monkeypatch) -> None:
    steps = importlib.import_module('bling_app_zero.ui.cadastro_wizard_steps')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    st.session_state['df_final_cadastro'] = pd.DataFrame([{'Descrição': 'Produto teste'}])
    st.session_state['mapping_cadastro'] = {'Descrição': 'Nome'}

    assert steps.cadastro_mapping_ready() is False

    st.session_state['cadastro_mapping_confirmed'] = True
    assert steps.cadastro_mapping_ready() is True


def test_cadastro_download_only_happens_on_download_step() -> None:
    preview_step = Path('bling_app_zero/ui/cadastro_preview_step.py').read_text(encoding='utf-8')
    download_step = Path('bling_app_zero/ui/cadastro_download_step.py').read_text(encoding='utf-8')

    assert 'download_final(' not in preview_step
    assert "download_final(df_final, 'cadastro', 'cadastro_wizard')" in download_step
    assert "preview_df('🧾 CADASTRO · Preview final', df_final)" in preview_step


def test_estoque_download_only_happens_on_download_step() -> None:
    preview_step = Path('bling_app_zero/ui/estoque_preview_step.py').read_text(encoding='utf-8')
    download_step = Path('bling_app_zero/ui/estoque_download_step.py').read_text(encoding='utf-8')

    assert 'render_stock_downloads()' not in preview_step
    assert 'render_stock_downloads()' in download_step
    assert 'render_stock_preview()' in preview_step


def test_download_final_uses_official_exporter() -> None:
    home_shared = Path('bling_app_zero/ui/home_shared.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.core.exporter import filename_for_operation, to_bling_csv_bytes' in home_shared
    assert 'to_bling_csv_bytes(df, operation=operation)' in home_shared
    assert '.to_csv(' not in home_shared


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
                'Descrição': 'Produto teste',
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

    assert 'Descrição' in header
    assert 'GTIN/EAN' in header
    assert 'URL imagens externas' in header
    assert row['GTIN/EAN'] == ''
    assert row['URL imagens externas'] == 'https://a.com/1.jpg|https://a.com/2.jpg'
