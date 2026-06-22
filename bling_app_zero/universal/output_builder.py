from __future__ import annotations

import re
from typing import Any

import pandas as pd

from bling_app_zero.core.text import normalize_key
from bling_app_zero.universal.model_fidelity import enforce_same_model_contract, reindex_exact_model_columns
from bling_app_zero.universal.universal_contract import UniversalContract, build_universal_contract, validate_universal_output

KEY_TERMS = (
    'codigo', 'código', 'sku', 'referencia', 'referência', 'id_na_loja', 'id loja', 'id_produto', 'id produto', 'idproduto'
)
PRICE_TERMS = ('preco', 'preço', 'valor')
PROMO_PRICE_TERMS = ('preco_promocional', 'preço_promocional', 'preco promocional', 'preço promocional', 'promocional')
CALCULATED_PRICE_COLUMNS = ('Preço de venda', 'Preco de venda')
CALCULATED_PROMO_PRICE_COLUMNS = ('Preço promocional', 'Preco Promocional', 'Preço Promocional')
NAME_TERMS = ('nome', 'descricao', 'descrição', 'produto', 'titulo', 'título')
TITLE_TARGET_TERMS = ('nome', 'titulo', 'título', 'title', 'name')
EMPTY_MARKERS = {'', 'nan', 'none', 'null', '<na>'}
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'


def _is_fixed_mapping_value(value: Any) -> bool:
    return str(value or '').startswith(FIXED_VALUE_PREFIX)


def _decode_fixed_mapping_value(value: Any) -> str:
    text = str(value or '')
    if text.startswith(FIXED_VALUE_PREFIX):
        return text[len(FIXED_VALUE_PREFIX):].strip()
    return text.strip()


def _fixed_series(value: Any, length: int) -> pd.Series:
    fixed_value = _decode_fixed_mapping_value(value)
    return pd.Series([fixed_value] * max(0, int(length or 0)), dtype='object')


def _clean_value(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def _is_empty(value: Any) -> bool:
    return _clean_value(value).lower() in EMPTY_MARKERS


def _norm_column(value: Any) -> str:
    return normalize_key(_clean_value(value)).replace(' ', '_')


def _has_term(column: Any, terms: tuple[str, ...]) -> bool:
    key = _norm_column(column)
    normalized_terms = tuple(normalize_key(term).replace(' ', '_') for term in terms)
    return any(term and term in key for term in normalized_terms)


def _is_title_target(column: Any) -> bool:
    key = _norm_column(column)
    normalized_terms = tuple(normalize_key(term).replace(' ', '_') for term in TITLE_TARGET_TERMS)
    return any(term and term in key for term in normalized_terms)


def _title_from_text(value: Any) -> str:
    """Extrai um título seguro quando a origem trouxe o nome dentro da descrição."""
    text = _clean_value(value)
    if _is_empty(text):
        return ''

    for separator in (' — ', ' – ', ' - ', ' | ', ' • ', '—', '–'):
        if separator in text:
            candidate = _clean_value(text.split(separator, 1)[0])
            if len(candidate) >= 3:
                return candidate

    sentence = re.split(r'(?<=[.!?])\s+', text, maxsplit=1)[0]
    candidate = _clean_value(sentence)
    if len(candidate) <= 120:
        return candidate
    return _clean_value(candidate[:120].rsplit(' ', 1)[0])


def _append_named_columns(out: list[str], columns: list[str], preferred: tuple[str, ...]) -> None:
    normalized_preferred = [_norm_column(column) for column in preferred]
    for wanted in normalized_preferred:
        for column in columns:
            if column not in out and _norm_column(column) == wanted:
                out.append(column)


def _append_columns(out: list[str], columns: list[str], terms: tuple[str, ...], *, exclude_terms: tuple[str, ...] = ()) -> None:
    for column in columns:
        if column in out:
            continue
        if exclude_terms and _has_term(column, exclude_terms):
            continue
        if _has_term(column, terms):
            out.append(column)


def _candidate_source_columns(df_source: pd.DataFrame, mapped_column: str, target_column: str) -> list[str]:
    if _is_fixed_mapping_value(mapped_column):
        return []
    columns = [str(column) for column in df_source.columns]
    out: list[str] = []

    is_promo_target = _has_term(target_column, PROMO_PRICE_TERMS)
    is_price_target = _has_term(target_column, PRICE_TERMS) and not is_promo_target

    if is_promo_target:
        _append_named_columns(out, columns, CALCULATED_PROMO_PRICE_COLUMNS)
    elif is_price_target:
        _append_named_columns(out, columns, CALCULATED_PRICE_COLUMNS)

    if mapped_column and mapped_column in columns and mapped_column not in out:
        out.append(mapped_column)

    target_key = _norm_column(target_column)
    for column in columns:
        if column not in out and _norm_column(column) == target_key:
            out.append(column)

    if is_promo_target:
        _append_columns(out, columns, PROMO_PRICE_TERMS)
        _append_columns(out, columns, PRICE_TERMS, exclude_terms=PROMO_PRICE_TERMS)
    elif is_price_target:
        _append_columns(out, columns, PRICE_TERMS, exclude_terms=PROMO_PRICE_TERMS)
        _append_columns(out, columns, PROMO_PRICE_TERMS)

    if _has_term(target_column, NAME_TERMS):
        for column in columns:
            if column not in out and _has_term(column, NAME_TERMS):
                out.append(column)
    return out


def _safe_series(df_source: pd.DataFrame, source_column: str, length: int) -> pd.Series:
    if isinstance(df_source, pd.DataFrame) and source_column in df_source.columns:
        return df_source[source_column].fillna('').astype(str).reset_index(drop=True)
    return pd.Series([''] * length, dtype='object')


def _prepare_candidate_value(value: Any, target_column: str) -> str:
    if _is_title_target(target_column):
        return _title_from_text(value)
    return _clean_value(value)


def _merged_candidate_series(df_source: pd.DataFrame, candidates: list[str], length: int, target_column: str) -> pd.Series:
    """Preenche linha a linha usando fallback entre colunas candidatas."""
    values = [''] * max(0, int(length or 0))
    for source_column in candidates:
        series = _safe_series(df_source, source_column, length)
        for idx in range(min(length, len(series))):
            if not _is_empty(values[idx]):
                continue
            candidate = _prepare_candidate_value(series.iloc[idx], target_column)
            if not _is_empty(candidate):
                values[idx] = candidate
    return pd.Series(values, dtype='object')


def _build_from_source_rows(df_source: pd.DataFrame, contract_columns: list[str], mapping: dict[str, str]) -> pd.DataFrame:
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    length = int(len(source)) if not source.empty else 0
    data: dict[str, pd.Series] = {}
    for target_column in contract_columns:
        source_column = str(mapping.get(target_column, '') or '')
        if _is_fixed_mapping_value(source_column):
            data[target_column] = _fixed_series(source_column, length)
            continue
        candidates = _candidate_source_columns(source, source_column, target_column)
        if not candidates and source_column:
            candidates = [source_column]
        data[target_column] = _merged_candidate_series(source, candidates, length, target_column) if candidates else pd.Series([''] * length, dtype='object')
    return pd.DataFrame(data, columns=contract_columns)


def build_universal_output(
    df_source: pd.DataFrame,
    df_model: pd.DataFrame,
    mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Gera saída com as colunas do modelo anexado e linhas da origem.

    Regra do fluxo universal:
    - o modelo anexado é contrato de colunas, ordem e nomes;
    - linhas de instrução/exemplo do modelo não entram no download;
    - cada linha da origem gera uma linha final;
    - valores fixos/manuais são repetidos na coluna inteira.
    """
    contract = build_universal_contract(df_model)
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    safe_mapping = mapping or {}

    df_output = _build_from_source_rows(source, contract.columns, safe_mapping)
    df_output = reindex_exact_model_columns(df_output, contract.columns)
    errors = validate_universal_output(df_output, contract)
    if errors:
        raise ValueError(' | '.join(errors))
    return enforce_same_model_contract(pd.DataFrame(columns=contract.columns), df_output)


def empty_universal_output(df_model: pd.DataFrame, rows: int = 0) -> pd.DataFrame:
    contract: UniversalContract = build_universal_contract(df_model)
    rows = max(0, int(rows or 0))
    return pd.DataFrame({column: [''] * rows for column in contract.columns}, columns=contract.columns)


__all__ = ['build_universal_output', 'empty_universal_output']
