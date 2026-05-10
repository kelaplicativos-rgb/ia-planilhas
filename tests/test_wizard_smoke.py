from __future__ import annotations

import csv
import importlib
from io import StringIO
from pathlib import Path

import pandas as pd


LIGHT_CRITICAL_MODULES = [
    'bling_app_zero.ui.home_wizard',
    'bling_app_zero.ui.cadastro_wizard_steps',
    'bling_app_zero.ui.estoque_wizard_steps',
    'bling_app_zero.ui.cadastro_mapping',
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


def test_wizard_step_order_is_preserved() -> None:
    wizard = importlib.import_module('bling_app_zero.ui.home_wizard')

    assert wizard.CADASTRO_STEPS == EXPECTED_CADASTRO_STEPS
    assert wizard.ESTOQUE_STEPS == EXPECTED_ESTOQUE_STEPS
    assert wizard.STEP_DOWNLOAD == 'download'
    assert wizard.STEP_GERAR_ESTOQUE == 'gerar_estoque'
    assert wizard.STEP_MAPEAMENTO == 'mapeamento'


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


def test_file_origin_does_not_reuse_old_site_origin() -> None:
    cadastro_steps = Path('bling_app_zero/ui/cadastro_wizard_steps.py').read_text(encoding='utf-8')
    estoque_steps = Path('bling_app_zero/ui/estoque_wizard_steps.py').read_text(encoding='utf-8')

    assert "df_origem_site = get_site_source_for_operation('cadastro') if site_origin else None" in cadastro_steps
    assert 'upload = render_cadastro_source_upload(None)' in cadastro_steps
    assert 'df_origem_site = get_estoque_site_source() if site_origin else None' in estoque_steps
    assert 'upload = render_estoque_upload(model_loaded)' in estoque_steps


def test_site_origin_uses_empty_upload_result() -> None:
    cadastro_steps = Path('bling_app_zero/ui/cadastro_wizard_steps.py').read_text(encoding='utf-8')
    estoque_steps = Path('bling_app_zero/ui/estoque_wizard_steps.py').read_text(encoding='utf-8')

    assert 'def _empty_upload_result() -> SmartUploadResult:' in cadastro_steps
    assert 'def _empty_upload_result() -> SmartUploadResult:' in estoque_steps
    assert 'if site_origin:\n        upload = _empty_upload_result()' in cadastro_steps
    assert 'if site_origin:\n        upload = _empty_upload_result()' in estoque_steps
    assert 'source_file=None' in cadastro_steps
    assert 'source_file=None' in estoque_steps


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
    cadastro_steps = Path('bling_app_zero/ui/cadastro_wizard_steps.py').read_text(encoding='utf-8')

    before_download_step = cadastro_steps.split('def render_cadastro_download_step()', 1)[0]
    download_step = cadastro_steps.split('def render_cadastro_download_step()', 1)[1]

    assert 'download_final(' not in before_download_step
    assert "download_final(df_final, 'cadastro', 'cadastro_wizard')" in download_step
    assert "preview_df('🧾 CADASTRO · Preview final', df_final)" in before_download_step


def test_mapping_css_uses_existing_theme_variables() -> None:
    mapping_css = Path('bling_app_zero/ui/layout/mapping.py').read_text(encoding='utf-8')

    assert '--bling-panel' not in mapping_css
    assert 'var(--bling-success)' not in mapping_css
    assert '--bling-surface' in mapping_css
    assert '--bling-success-text' in mapping_css


def test_download_final_uses_official_exporter() -> None:
    home_shared = Path('bling_app_zero/ui/home_shared.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.core.exporter import to_bling_csv_bytes' in home_shared
    assert 'data=to_bling_csv_bytes(df)' in home_shared
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
