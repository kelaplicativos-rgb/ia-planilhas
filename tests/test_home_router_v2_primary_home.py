from pathlib import Path


def test_home_router_v2_prioritizes_mapear_planilha_sem_api() -> None:
    source = Path('bling_app_zero/ui/home_router_v2.py').read_text(encoding='utf-8')

    assert 'def _render_primary_home()' in source
    assert "Mapear planilha sem API" in source
    assert "Conectar ou usar Bling" in source
    assert "Atualizar preços multilojas" in source
    assert "legacy.render_home()" in source

    primary_index = source.index('def _render_primary_home()')
    mapear_index = source.index('_render_mapear_planilha_primary_card()', primary_index)
    bling_index = source.index('_render_bling_api_card()', primary_index)
    price_index = source.index('_render_price_multistore_home_entry()', primary_index)

    assert mapear_index < bling_index < price_index
    assert 'legacy.render_home()\n    _render_mapear_planilha_home_entry()' not in source
    assert 'def _render_mapear_planilha_home_entry()' not in source
