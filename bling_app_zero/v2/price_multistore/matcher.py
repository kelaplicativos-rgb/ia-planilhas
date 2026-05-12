from __future__ import annotations

import pandas as pd


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    table = str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç', 'aaaaaeeeeiiiiooooouuuuc')
    text = text.translate(table)
    return ''.join(ch for ch in text if ch.isalnum())


IDENTIFIER_CANDIDATES = {
    'id_store': ('ID na Loja', 'Id na loja', 'ID Loja', 'ID Anuncio', 'ID Anúncio', 'Sku Marketplace'),
    'id_product': ('IdProduto', 'ID Produto', 'Codigo Produto', 'Código Produto'),
    'sku': ('SKU', 'Codigo', 'Código', 'Referencia', 'Referência'),
    'gtin': ('GTIN', 'EAN', 'GTIN/EAN'),
    'description': ('Descricao', 'Descrição', 'Produto', 'Nome'),
}


def find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    if not isinstance(df, pd.DataFrame):
        return ''
    normalized = {_norm(column): str(column) for column in df.columns}
    for candidate in candidates:
        found = normalized.get(_norm(candidate))
        if found:
            return found
    return ''


def find_best_identifier(model_df: pd.DataFrame, source_df: pd.DataFrame) -> tuple[str, str, str]:
    for kind, candidates in IDENTIFIER_CANDIDATES.items():
        model_col = find_column(model_df, candidates)
        source_col = find_column(source_df, candidates)
        if model_col and source_col:
            return kind, model_col, source_col
    return '', '', ''


def merge_source_cost(
    model_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_cost_column: str,
    output_cost_column: str = '_v2_custo_base',
) -> pd.DataFrame:
    base = model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame()
    source = source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base
    if source.empty or source_cost_column not in source.columns:
        base[output_cost_column] = ''
        return base

    _kind, model_id, source_id = find_best_identifier(base, source)
    if not model_id or not source_id:
        base[output_cost_column] = ''
        return base

    lookup_cost_column = f'{output_cost_column}_origem'
    lookup = source[[source_id, source_cost_column]].copy().fillna('')
    lookup[source_id] = lookup[source_id].astype(str).str.strip()
    lookup = lookup.rename(columns={source_cost_column: lookup_cost_column})
    lookup = lookup.drop_duplicates(subset=[source_id], keep='first')

    out = base.copy().fillna('')
    out[model_id] = out[model_id].astype(str).str.strip()
    out = out.merge(lookup, how='left', left_on=model_id, right_on=source_id, suffixes=('', '_match'))
    out[output_cost_column] = out.get(lookup_cost_column, '').fillna('') if lookup_cost_column in out.columns else ''

    drop_cols = [column for column in [source_id, lookup_cost_column] if column in out.columns and column not in base.columns]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    return out.fillna('')


__all__ = ['find_best_identifier', 'find_column', 'merge_source_cost']
