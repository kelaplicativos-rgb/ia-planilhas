from __future__ import annotations

import pandas as pd

from bling_app_zero.core.text import normalize_key


def validate_final_df(df: pd.DataFrame, operation: str) -> list[str]:
    errors: list[str] = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ['O arquivo final ainda está vazio. Confira a origem dos dados antes de baixar.']

    columns = [str(c) for c in df.columns]
    keys = [normalize_key(c) for c in columns]
    op = normalize_key(operation)

    if op == 'cadastro':
        if not any('descricao' in key or 'nome' in key for key in keys):
            errors.append('Cadastro: falta um campo de nome ou descrição do produto.')
        if not any('preco' in key or 'valor' in key for key in keys):
            errors.append('Cadastro: falta um campo de preço ou valor.')

    if op == 'estoque':
        if not any('codigo' in key or 'sku' in key or 'referencia' in key for key in keys):
            errors.append('Estoque: falta um campo de código, SKU ou referência do produto.')
        if not any('estoque' in key or 'balanco' in key or 'quantidade' in key or 'saldo' in key for key in keys):
            errors.append('Estoque: falta um campo de saldo, quantidade, balanço ou estoque.')

    return errors
