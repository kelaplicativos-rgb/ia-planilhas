from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.universal_flow import _is_technical_error_frame


def test_universal_flow_detects_binary_error_frame_as_invalid_contract() -> None:
    df = pd.DataFrame(
        {
            'Arquivo': ['produtos.xlsx'],
            'Status': ['Arquivo binário recebido; não foi possível extrair tabela automaticamente.'],
        }
    )

    assert _is_technical_error_frame(df) is True


def test_universal_flow_does_not_block_real_product_model_with_status_column() -> None:
    df = pd.DataFrame(
        {
            'Código': ['P001'],
            'Descrição': ['Produto teste'],
            'Status': ['Ativo'],
            'Preço': ['10,00'],
        }
    )

    assert _is_technical_error_frame(df) is False
