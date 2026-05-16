from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_contract_adapter_preserves_model_exactly() -> None:
    from bling_app_zero.universal.contract_adapter import adapt_dataframe_to_model_contract

    df = pd.DataFrame(
        [
            {
                'Produto': 'Mouse',
                'Valor': '29,90',
                'Extra': 'remover',
            }
        ]
    )
    model = pd.DataFrame(columns=['Valor', 'Produto', 'Campo vazio'])

    adapted = adapt_dataframe_to_model_contract(df, model)

    assert list(adapted.columns) == ['Valor', 'Produto', 'Campo vazio']
    assert adapted.iloc[0].to_dict() == {
        'Valor': '29,90',
        'Produto': 'Mouse',
        'Campo vazio': '',
    }
    assert 'Extra' not in adapted.columns


def test_contract_adapter_keeps_df_when_no_model() -> None:
    from bling_app_zero.universal.contract_adapter import adapt_dataframe_to_model_contract

    df = pd.DataFrame([{'A': '1', 'B': '2'}])
    adapted = adapt_dataframe_to_model_contract(df, None)

    assert list(adapted.columns) == ['A', 'B']
    assert adapted.iloc[0].to_dict() == {'A': '1', 'B': '2'}


def test_download_final_uses_model_contract_adapter() -> None:
    home_shared = Path('bling_app_zero/ui/home_shared.py').read_text(encoding='utf-8')

    assert 'adapt_dataframe_to_model_contract' in home_shared
    assert 'model_for_operation' in home_shared
    assert 'def _download_dataframe_for_contract' in home_shared
    assert 'download_df, contract_applied, model_columns = _download_dataframe_for_contract(df, operation)' in home_shared
    assert 'to_bling_csv_bytes(df.copy()' not in home_shared
    assert 'to_bling_csv_bytes(download_df.copy()' in home_shared
    assert 'Download fiel ao modelo anexado' in home_shared
