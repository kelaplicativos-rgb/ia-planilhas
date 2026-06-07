import pandas as pd

from bling_app_zero.core.final_csv_exporter import final_csv_bytes, physical_csv_contract_errors, sanitize_final_dataframe


def test_final_csv_remove_ponto_virgula_e_preserva_contrato():
    contract = ['Codigo', 'Descricao', 'Fornecedor']
    df = pd.DataFrame([{'Codigo': 'ABC123', 'Descricao': 'Produto com texto; e quebra\nde linha', 'Fornecedor': 'B2Drop', 'Extra': 'nao pode sair'}])
    safe = sanitize_final_dataframe(df, contract_columns=contract, run_download_features=False)
    assert list(safe.columns) == contract
    assert 'Extra' not in safe.columns
    assert ';' not in safe.loc[0, 'Descricao']
    data = final_csv_bytes(df, contract_columns=contract, run_download_features=False)
    assert physical_csv_contract_errors(data, expected_columns=len(contract)) == []


def test_final_csv_mantem_fornecedor_no_df_final():
    contract = ['Codigo', 'Fornecedor', 'Cod no fornecedor']
    df = pd.DataFrame([{'Codigo': 'DQEAPPAVCS0002', 'Fornecedor': 'B2Drop', 'Cod no fornecedor': 'DQEAPPAVCS0002'}])
    safe = sanitize_final_dataframe(df, contract_columns=contract, run_download_features=False)
    assert list(safe.columns) == contract
    assert safe.loc[0, 'Fornecedor'] == 'B2Drop'
    assert safe.loc[0, 'Cod no fornecedor'] == 'DQEAPPAVCS0002'
