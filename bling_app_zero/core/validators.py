from __future__ import annotations

import pandas as pd

from bling_app_zero.core.text import normalize_key


def validate_final_df(df: pd.DataFrame, operation: str) -> list[str]:
    errors: list[str] = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ['A planilha final está vazia.']

    columns = [str(c) for c in df.columns]
    keys = [normalize_key(c) for c in columns]
    op = normalize_key(operation)

    if op == 'cadastro':
        if not any('descricao' in key or 'nome' in key for key in keys):
            errors.append('Cadastro precisa ter coluna de descrição/nome.')
        if not any('preco' in key or 'valor' in key for key in keys):
            errors.append('Cadastro precisa ter coluna de preço/valor.')

    if op == 'estoque':
        if not any('codigo' in key or 'sku' in key or 'referencia' in key for key in keys):
            errors.append('Estoque precisa ter código/SKU/referência.')
        if not any('estoque' in key or 'balanco' in key or 'quantidade' in key or 'saldo' in key for key in keys):
            errors.append('Estoque precisa ter saldo/quantidade/balanço.')

    return errors
