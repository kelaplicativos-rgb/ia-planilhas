from __future__ import annotations

import pandas as pd


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    table = str.maketrans('áàãâäéèêëíìîïóòõöúùûüç', 'aaaaaeeeeiiiioooouuuuc')
    text = text.translate(table)
    return ''.join(ch for ch in text if ch.isalnum())


IDENTIFIER_CANDIDATES = {
    'id_store': ('ID na Loja', 'Id na loja', 'ID Loja', 'ID Anuncio', 'ID Anúncio', 'Sku Marketplace'),
    'id_product': ('IdProduto', 'ID Produto', 'Codigo Produto', 'Código Produto'),
    'sku': ('SKU', 'Codigo', 'Código', 'Referencia', 'Referência'),
    'gtin': ('GTIN', 'EAN', 'GTIN/EAN'),
    'description': ('Descricao', 'Descrição', 'Produto', 'Nome'),
}


KIND_LABELS = {
    'manual': 'Mapeamento manual',
    'id_store': 'ID na Loja',
    'id_product': 'IdProduto',
    'sku': 'SKU/Código',
    'gtin': 'GTIN/EAN',
    'description': 'Descrição/Nome',
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


def _clean_match_key(series: pd.Series) -> pd.Series:
    return series.fillna('').astype(str).str.strip()


def _resolve_identifier_columns(
    base: pd.DataFrame,
    source: pd.DataFrame,
    model_identifier_column: str = '',
    source_identifier_column: str = '',
) -> tuple[str, str, str]:
    model_col = str(model_identifier_column or '').strip()
    source_col = str(source_identifier_column or '').strip()
    if model_col in base.columns and source_col in source.columns:
        return 'manual', model_col, source_col
    return find_best_identifier(base, source)


def merge_source_cost(
    model_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_cost_column: str,
    output_cost_column: str = '_v2_custo_base',
    model_identifier_column: str = '',
    source_identifier_column: str = '',
) -> pd.DataFrame:
    base = model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame()
    source = source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return base
    if source.empty or source_cost_column not in source.columns:
        base[output_cost_column] = ''
        return base

    _kind, model_id, source_id = _resolve_identifier_columns(base, source, model_identifier_column, source_identifier_column)
    if not model_id or not source_id:
        base[output_cost_column] = ''
        return base

    lookup_cost_column = f'{output_cost_column}_origem'
    lookup = source[[source_id, source_cost_column]].copy().fillna('')
    lookup[source_id] = _clean_match_key(lookup[source_id])
    lookup = lookup.rename(columns={source_cost_column: lookup_cost_column})
    lookup = lookup.drop_duplicates(subset=[source_id], keep='first')

    out = base.copy().fillna('')
    out[model_id] = _clean_match_key(out[model_id])
    out = out.merge(lookup, how='left', left_on=model_id, right_on=source_id, suffixes=('', '_match'))
    out[output_cost_column] = out.get(lookup_cost_column, '').fillna('') if lookup_cost_column in out.columns else ''

    drop_cols = [column for column in [source_id, lookup_cost_column] if column in out.columns and column not in base.columns]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    return out.fillna('')


def build_not_included_audit(
    model_df: pd.DataFrame,
    source_df: pd.DataFrame | None,
    source_cost_column: str = '',
    model_identifier_column: str = '',
    source_identifier_column: str = '',
) -> pd.DataFrame:
    """Lista produtos da origem que não entraram na operação multiloja."""
    base = model_df.copy().fillna('') if isinstance(model_df, pd.DataFrame) else pd.DataFrame()
    source = source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) else pd.DataFrame()
    if base.empty or source.empty:
        return pd.DataFrame()

    kind, model_id, source_id = _resolve_identifier_columns(base, source, model_identifier_column, source_identifier_column)
    if not model_id or not source_id:
        audit = source.copy().fillna('')
        audit.insert(0, 'Motivo auditoria', 'Sem identificador comum para cruzar com a planilha do Bling')
        audit.insert(1, 'Identificador usado', '')
        audit.insert(2, 'Coluna origem', '')
        audit.insert(3, 'Coluna Bling', '')
        if source_cost_column and source_cost_column in audit.columns:
            audit.insert(4, 'Coluna de custo selecionada', source_cost_column)
        return audit.fillna('')

    model_keys = set(_clean_match_key(base[model_id]))
    model_keys.discard('')

    source_keys = _clean_match_key(source[source_id])
    mask_not_included = ~source_keys.isin(model_keys)
    mask_not_included |= source_keys.eq('')

    audit = source.loc[mask_not_included].copy().fillna('')
    if audit.empty:
        return pd.DataFrame()

    audit.insert(0, 'Motivo auditoria', 'Produto da origem não encontrado na Planilha 1 do Bling')
    audit.insert(1, 'Identificador usado', KIND_LABELS.get(kind, kind))
    audit.insert(2, 'Valor do identificador', source_keys.loc[mask_not_included].values)
    audit.insert(3, 'Coluna origem', source_id)
    audit.insert(4, 'Coluna Bling', model_id)
    if source_cost_column:
        audit.insert(5, 'Coluna de custo selecionada', source_cost_column)
    return audit.fillna('')


__all__ = ['build_not_included_audit', 'find_best_identifier', 'find_column', 'merge_source_cost']