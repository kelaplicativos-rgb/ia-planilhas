from __future__ import annotations

from pathlib import Path


def test_mapping_confirmation_uses_flow_blocker_for_invalid_mapping() -> None:
    source = Path('bling_app_zero/ui/mapping_confirmation.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Mapeamento bloqueado' in source
    assert 'Campos obrigatórios sem ligação' in source
    assert 'Colunas de origem repetidas' in source


def test_cadastro_manual_mapping_blocks_duplicate_source_columns() -> None:
    source = Path('bling_app_zero/ui/mapping_cadastro_flow.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Coluna repetida:' in source
    assert 'Confirmar mapeamento' in source


def test_stock_manual_mapping_blocks_duplicate_source_columns_and_missing_model() -> None:
    source = Path('bling_app_zero/ui/mapping_estoque_flow.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'A mesma coluna da origem foi usada mais de uma vez no estoque' in source
    assert 'Estoque bloqueado' in source
    assert 'Envie o modelo de estoque no passo inicial' in source


def test_stock_mapping_step_uses_flow_blocker_for_missing_source_or_model() -> None:
    source = Path('bling_app_zero/ui/estoque_mapping_step.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Mapeamento de estoque bloqueado' in source
    assert 'Modelo de destino ausente' in source
    assert 'Nenhuma origem de dados carregada' in source


def test_stock_site_panel_uses_standard_blockers() -> None:
    source = Path('bling_app_zero/ui/estoque_site_panel.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'from bling_app_zero.ui.alerts import render_alert' in source
    assert 'Busca por site bloqueada' in source
    assert 'Informe pelo menos um link' in source
    assert 'unsafe_allow_html=True' in source  # card visual da tela ainda usa layout HTML controlado
    assert '<div style=' not in source


def test_stock_outputs_use_flow_blockers_for_missing_results() -> None:
    source = Path('bling_app_zero/ui/estoque_outputs.py').read_text(encoding='utf-8')

    assert 'from bling_app_zero.ui.flow_guard import render_flow_blocker' in source
    assert 'Nenhuma origem válida de estoque foi encontrada' in source
    assert 'Preview de estoque bloqueado' in source
    assert 'Download de estoque bloqueado' in source
    assert 'Nenhuma planilha de estoque foi gerada ainda' in source
