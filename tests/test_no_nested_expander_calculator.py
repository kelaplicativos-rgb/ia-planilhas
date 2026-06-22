from __future__ import annotations

from pathlib import Path


def test_shared_calculator_has_no_nested_advanced_expander() -> None:
    path = Path('bling_app_zero/ui/shared_calculator.py')
    content = path.read_text(encoding='utf-8')

    assert "with st.expander('Avançado: coluna auxiliar diferente'" not in content
    assert 'Avançado: usar nome técnico diferente da coluna do modelo' in content
    assert 'with st.container(border=True):' in content
