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
    'bling_app_zero.ui.home_autofluxo',
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
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.gtin',
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
    for module_name in ['bling_app_zero.ui.site_panel', 'bling_app_zero.ui.site_outputs']:
        importlib.import_module(module_name)


def test_streamlit_entrypoint_uses_home_wizard() -> None:
    app_source = Path('app.py').read_text(encoding='utf-8')
    home_source = Path('bling_app_zero/ui/home.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.home import render_home' in app_source
    assert 'render_home()' in app_source
    assert 'from bling_app_zero.ui.home_wizard import render_home_wizard' in home_source
    assert 'from bling_app_zero.ui.wizard_state_guard import run_wizard_state_guard' in home_source
    assert 'run_home_autofluxo()' in home_source
    assert 'render_home_wizard()' in home_source


def test_wizard_step_order_is_preserved() -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')

    assert wizard.CADASTRO_STEPS == EXPECTED_CADASTRO_STEPS
    assert wizard.ESTOQUE_STEPS == EXPECTED_ESTOQUE_STEPS
    assert 'precificacao' not in wizard.ESTOQUE_STEPS
    assert wizard.STEP_DOWNLOAD == 'download'
    assert wizard.STEP_GERAR_ESTOQUE == 'gerar_estoque'
    assert wizard.STEP_MAPEAMENTO == 'mapeamento'
    assert wizard.STEP_REGRAS == 'regras'


def _assert_linear_navigation(wizard, operation: str, steps: list[str]) -> None:
    assert wizard.wizard_steps_for_operation(operation) == steps
    for index, step in enumerate(steps):
        expected_previous = steps[max(0, index - 1)]
        expected_next = steps[min(len(steps) - 1, index + 1)]
        assert wizard.wizard_previous_target(step, operation) in {expected_previous, wizard.HOME_CHOICE_TARGET}
        if index > 0:
            assert wizard.wizard_previous_target(step, operation) == expected_previous
        assert wizard.wizard_next_target(step, operation) == expected_next


def test_wizard_button_flowchart_cadastro() -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')
    _assert_linear_navigation(wizard, 'cadastro', EXPECTED_CADASTRO_STEPS)


def test_wizard_button_flowchart_estoque_sem_preco() -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')
    _assert_linear_navigation(wizard, 'estoque', EXPECTED_ESTOQUE_STEPS)
    assert wizard.wizard_next_target('operacao', 'estoque') == 'origem'
    assert wizard.wizard_previous_target('origem', 'estoque') == 'operacao'


def test_bottom_navigation_blocks_without_disabled_continue_button() -> None:
    wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')

    assert 'BOTTOM_NAV_RENDERED_KEY' in wizard
    assert "data-testid=\"wizard-bottom-navigation\"" in wizard
    assert "st.button('← Voltar'" in wizard
    assert "st.button(next_label" in wizard
    assert 'render_pending_notice(pending_message)' in wizard
    assert 'wizard_bottom_next_disabled' not in wizard
    assert "st.button('Avançar →', use_container_width=True, disabled=True" not in wizard


def test_origin_step_auto_advances_after_selection() -> None:
    wizard = Path('bling_app_zero/ui/home_wizard.py').read_text(encoding='utf-8')
    origin_block = wizard.split('def _render_origin_step() -> None:', 1)[1].split('def _render_rules_step() -> None:', 1)[0]

    assert '_sync_flow_state(origin, operation)' in origin_block
    assert 'origin_selected_auto_next' in origin_block
    assert 'wizard_next_target(STEP_ORIGEM, operation)' in origin_block
    assert 'Avançando para a próxima etapa.' in origin_block


def test_autofluxo_is_safe_enabled_by_default() -> None:
    autofluxo = Path('bling_app_zero/ui/home_autofluxo.py').read_text(encoding='utf-8')

    assert 'def _autoflow_enabled() -> bool:' in autofluxo
    assert 'st.session_state[AUTOFLOW_ENABLED_KEY] = True' in autofluxo
    assert 'st.session_state.get(AUTOFLOW_ENABLED_KEY, True)' in autofluxo
    assert 'MANUAL_REVIEW_STEPS = {STEP_MAPEAMENTO, STEP_GERAR_ESTOQUE}' in autofluxo
    assert 'current in {STEP_PREVIEW, STEP_DOWNLOAD}' in autofluxo
    assert "operation == 'cadastro' and not _pricing_is_active()" in autofluxo


def test_cadastro_mapping_ready_requires_manual_confirmation(monkeypatch) -> None:
    steps = importlib.import_module('bling_app_zero.ui.cadastro_wizard_steps')
    st = importlib.import_module('streamlit')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    st.session_state['df_final_cadastro'] = pd.DataFrame([{'Descricao': 'Produto teste'}])
    st.session_state['mapping_cadastro'] = {'Descricao': 'Nome'}

    assert steps.cadastro_mapping_ready() is False

    st.session_state['cadastro_mapping_confirmed'] = True
    assert steps.cadastro_mapping_ready() is True


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
