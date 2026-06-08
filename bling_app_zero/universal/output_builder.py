from __future__ import annotations

import re
from typing import Any

import pandas as pd

from bling_app_zero.core.text import normalize_key
from bling_app_zero.universal.universal_contract import UniversalContract, build_universal_contract, validate_universal_output

KEY_TERMS = (
    'codigo', 'código', 'sku', 'referencia', 'referência', 'id_na_loja', 'id loja', 'id_produto', 'id produto', 'idproduto'
)
PRICE_TERMS = ('preco', 'preço', 'valor', 'preco_promocional', 'preço_promocional', 'preco promocional', 'preço promocional')
NAME_TERMS = ('nome', 'descricao', 'descrição', 'produto', 'titulo', 'título')
EMPTY_MARKERS = {'', 'nan', 'none', 'null', '<na>'}


def _clean_value(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def _is_empty(value: Any) -> bool:
    return _clean_value(value).lower() in EMPTY_MARKERS


def _norm_column(value: Any) -> str:
    return normalize_key(_clean_value(value)).replace(' ', '_')


def _norm_match_value(value: Any) -> str:
    text = _clean_value(value).lower()
    text = text.replace('\t', ' ')
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[^a-z0-9_-]+', '', text)
    return text.strip()


def _has_term(column: Any, terms: tuple[str, ...]) -> bool:
    key = _norm_column(column)
    normalized_terms = tuple(normalize_key(term).replace(' ', '_') for term in terms)
    return any(term and term in key for term in normalized_terms)


def _key_columns(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    preferred: list[str] = []
    secondary: list[str] = []
    for column in df.columns:
        key = _norm_column(column)
        if key in {'codigo', 'código', 'sku', 'referencia', 'referência', 'id_na_loja'}:
            preferred.append(str(column))
        elif _has_term(column, KEY_TERMS):
            secondary.append(str(column))
    return preferred + [column for column in secondary if column not in preferred]


def _candidate_source_columns(df_source: pd.DataFrame, mapped_column: str, target_column: str) -> list[str]:
    columns = [str(column) for column in df_source.columns]
    out: list[str] = []
    if mapped_column and mapped_column in columns:
        out.append(mapped_column)
    target_key = _norm_column(target_column)
    for column in columns:
        if column not in out and _norm_column(column) == target_key:
            out.append(column)
    if _has_term(target_column, PRICE_TERMS):
        for column in columns:
            if column not in out and _has_term(column, PRICE_TERMS):
                out.append(column)
    if _has_term(target_column, NAME_TERMS):
        for column in columns:
            if column not in out and _has_term(column, NAME_TERMS):
                out.append(column)
    return out


def _build_lookup(df_source: pd.DataFrame, source_value_column: str) -> dict[str, str]:
    lookup: dict[str, str] = {}
    source_keys = _key_columns(df_source)
    if not source_keys or source_value_column not in df_source.columns:
        return lookup
    for _, row in df_source.fillna('').astype(str).iterrows():
        value = _clean_value(row.get(source_value_column, ''))
        if _is_empty(value):
            continue
        for key_column in source_keys:
            key_value = _norm_match_value(row.get(key_column, ''))
            if key_value and key_value not in lookup:
                lookup[key_value] = value
    return lookup


def _match_model_row(row: pd.Series, lookup: dict[str, str], model_key_columns: list[str]) -> str:
    for key_column in model_key_columns:
        key_value = _norm_match_value(row.get(key_column, ''))
        if key_value and key_value in lookup:
            return lookup[key_value]
    return ''


def _safe_series(df_source: pd.DataFrame, source_column: str, length: int) -> pd.Series:
    if isinstance(df_source, pd.DataFrame) and source_column in df_source.columns:
        return df_source[source_column].fillna('').astype(str).reset_index(drop=True)
    return pd.Series([''] * length, dtype='object')


def _build_from_empty_model(df_source: pd.DataFrame, contract_columns: list[str], mapping: dict[str, str]) -> pd.DataFrame:
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    length = int(len(source)) if not source.empty else 0
    data: dict[str, pd.Series] = {}
    for target_column in contract_columns:
        source_column = str(mapping.get(target_column, '') or '')
        data[target_column] = _safe_series(source, source_column, length)
    return pd.DataFrame(data, columns=contract_columns)


def _build_from_filled_model(df_source: pd.DataFrame, df_model: pd.DataFrame, contract_columns: list[str], mapping: dict[str, str]) -> pd.DataFrame:
    """Preenche um modelo já exportado pelo Bling usando a origem como atualização.

    Para modelos como preços multiloja, o arquivo do Bling vem com linhas reais
    contendo IdProduto, ID na Loja, Código, Nome e Loja. Esse arquivo não pode ser
    tratado como modelo vazio. A regra correta é preservar todas as linhas e
    atualizar apenas as colunas mapeadas com dados vindos da origem, casando por
    Código/SKU/ID na Loja sempre que possível.
    """
    model = df_model.reindex(columns=contract_columns, fill_value='').copy().fillna('').astype(str).reset_index(drop=True)
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    if source.empty:
        return model

    model_key_columns = _key_columns(model)
    same_length = len(source) == len(model)

    for target_column in contract_columns:
        mapped_column = str(mapping.get(target_column, '') or '')
        candidates = _candidate_source_columns(source, mapped_column, target_column)
        if not candidates:
            continue

        applied = False
        for source_column in candidates:
            lookup = _build_lookup(source, source_column)
            if lookup and model_key_columns:
                values = model.apply(lambda row: _match_model_row(row, lookup, model_key_columns), axis=1)
                mask = values.map(lambda value: not _is_empty(value))
                if bool(mask.any()):
                    model.loc[mask, target_column] = values[mask]
                    applied = True
                    break

        if applied:
            continue

        if same_length and mapped_column in source.columns:
            values = source[mapped_column].fillna('').astype(str).reset_index(drop=True)
            mask = values.map(lambda value: not _is_empty(value))
            if bool(mask.any()):
                model.loc[mask, target_column] = values[mask]

    return model.reindex(columns=contract_columns, fill_value='').fillna('')


def build_universal_output(
    df_source: pd.DataFrame,
    df_model: pd.DataFrame,
    mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Gera saída idêntica ao modelo anexado.

    Regra central do MapeiaAI:
    - mesmas colunas do modelo;
    - mesma ordem do modelo;
    - sem colunas extras;
    - modelo vazio cria linhas a partir da origem;
    - modelo preenchido preserva as linhas do Bling e atualiza pelos dados da origem.
    """
    contract = build_universal_contract(df_model)
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    model = df_model if isinstance(df_model, pd.DataFrame) else pd.DataFrame(columns=contract.columns)
    safe_mapping = mapping or {}

    if isinstance(model, pd.DataFrame) and not model.empty:
        df_output = _build_from_filled_model(source, model, contract.columns, safe_mapping)
    else:
        df_output = _build_from_empty_model(source, contract.columns, safe_mapping)

    errors = validate_universal_output(df_output, contract)
    if errors:
        raise ValueError(' | '.join(errors))
    return df_output


def empty_universal_output(df_model: pd.DataFrame, rows: int = 0) -> pd.DataFrame:
    contract: UniversalContract = build_universal_contract(df_model)
    rows = max(0, int(rows or 0))
    return pd.DataFrame({column: [''] * rows for column in contract.columns}, columns=contract.columns)


__all__ = ['build_universal_output', 'empty_universal_output']
