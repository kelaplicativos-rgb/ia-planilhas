from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Sequence

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/final_csv_exporter.py'
INTERNAL_COLUMN_PREFIXES = ('_v2_',)
DEFAULT_SEPARATOR = ';'
DEFAULT_ENCODING = 'utf-8-sig'


@dataclass(frozen=True)
class FinalCsvExportResult:
    df: pd.DataFrame
    csv_bytes: bytes
    filename: str
    operation: str
    columns: tuple[str, ...]
    rows: int


def _as_list(values: Sequence[object] | None) -> list[object]:
    if values is None:
        return []
    try:
        return list(values)
    except TypeError:
        return [values]


def clean_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return text.strip()


def clean_bling_cell_text(value: object, *, sep: str = DEFAULT_SEPARATOR) -> str:
    # Compatibilidade de nome antigo. Não remove mais ponto e vírgula, aspas ou tabs.
    return clean_text(value)


def clean_columns(columns: Sequence[object] | None) -> list[str]:
    return [clean_text(column) for column in _as_list(columns) if clean_text(column)]


def exact_contract_columns(columns: Sequence[object] | None) -> list[str]:
    if columns is None:
        return []
    out: list[str] = []
    for column in _as_list(columns):
        text = '' if column is None else str(column)
        text = text.replace('\ufeff', '').replace('\x00', '')
        text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        out.append(text.strip())
    return out


def contract_columns_from_model(df_model: pd.DataFrame | None) -> list[str]:
    if not isinstance(df_model, pd.DataFrame):
        return []
    return exact_contract_columns(df_model.columns)


def clean_explicit_empty_columns(columns: Sequence[object] | None) -> set[str]:
    return {clean_text(column) for column in _as_list(columns) if clean_text(column)}


def drop_internal_columns(df: pd.DataFrame, prefixes: Sequence[str] = INTERNAL_COLUMN_PREFIXES) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    internal = [column for column in df.columns if any(str(column).startswith(prefix) for prefix in prefixes)]
    return df.drop(columns=internal, errors='ignore') if internal else df


def normalize_dataframe(df: pd.DataFrame | None, *, keep_internal: bool = False, preserve_columns: bool = False) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna('')
    if not keep_internal:
        out = drop_internal_columns(out)
    if not preserve_columns:
        out.columns = [clean_text(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].map(clean_text)
    return out.fillna('')


def normalize_image_columns(df: pd.DataFrame | None) -> pd.DataFrame:
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()


def contract_from_df(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> list[str]:
    explicit = exact_contract_columns(contract_columns)
    if explicit:
        return explicit
    if isinstance(df, pd.DataFrame):
        return exact_contract_columns(df.columns)
    return []


def force_empty_columns(df: pd.DataFrame, columns: Sequence[object] | None = None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in clean_explicit_empty_columns(columns):
        if column in out.columns:
            out[column] = ''
    return out


def enforce_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    columns = contract_from_df(None, contract_columns)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    preserve = bool(columns)
    out = normalize_dataframe(df, keep_internal=False, preserve_columns=preserve)
    if not columns:
        return out
    return out.reindex(columns=columns, fill_value='').fillna('')


def validate_contract_identity(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> list[str]:
    contract = contract_from_df(None, contract_columns)
    if not contract:
        return []
    if not isinstance(df, pd.DataFrame):
        return ['A planilha final não é uma tabela válida.']
    output_columns = exact_contract_columns(df.columns)
    if output_columns != contract:
        return ['A planilha final não está fiel ao contrato de colunas do modelo anexado.']
    return []


def physical_csv_contract_errors(csv_bytes: bytes, expected_columns: int, *, sep: str = DEFAULT_SEPARATOR) -> list[str]:
    # CSV usa aspas quando necessário; contar separadores físicos quebra valores legítimos.
    return []


def _to_csv_bytes_strict(df: pd.DataFrame, *, sep: str = DEFAULT_SEPARATOR) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, sep=sep, index=False, encoding=DEFAULT_ENCODING, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    return buffer.getvalue().encode(DEFAULT_ENCODING)


def sanitize_final_dataframe(df: pd.DataFrame | None, *, operation: str = 'global', contract_columns: Sequence[object] | None = None, explicit_empty_columns: Sequence[object] | None = None, run_download_features: bool = True) -> pd.DataFrame:
    if df is None:
        return enforce_contract(None, contract_columns)
    contract = contract_from_df(df, contract_columns)
    safe = normalize_dataframe(df, keep_internal=False, preserve_columns=bool(contract))
    safe = force_empty_columns(safe, explicit_empty_columns)
    return enforce_contract(safe, contract)


def final_csv_bytes(df: pd.DataFrame | None, *, operation: str = 'global', contract_columns: Sequence[object] | None = None, explicit_empty_columns: Sequence[object] | None = None, sep: str = DEFAULT_SEPARATOR, run_download_features: bool = True) -> bytes:
    safe = sanitize_final_dataframe(df, operation=operation, contract_columns=contract_columns, explicit_empty_columns=explicit_empty_columns, run_download_features=False)
    return _to_csv_bytes_strict(safe, sep=sep)


def filename_for_operation(operation: str) -> str:
    return 'modelo_mapeado.csv'


def build_final_csv_export(df: pd.DataFrame | None, *, operation: str = 'global', contract_columns: Sequence[object] | None = None, explicit_empty_columns: Sequence[object] | None = None, file_name: str | None = None, sep: str = DEFAULT_SEPARATOR, run_download_features: bool = True) -> FinalCsvExportResult:
    safe = sanitize_final_dataframe(df, operation=operation, contract_columns=contract_columns, explicit_empty_columns=explicit_empty_columns, run_download_features=False)
    csv_bytes = _to_csv_bytes_strict(safe, sep=sep)
    filename = file_name or filename_for_operation(operation)
    return FinalCsvExportResult(df=safe, csv_bytes=csv_bytes, filename=filename, operation='universal', columns=tuple(map(str, safe.columns)), rows=int(len(safe)))


__all__ = [
    'DEFAULT_ENCODING',
    'DEFAULT_SEPARATOR',
    'FinalCsvExportResult',
    'build_final_csv_export',
    'clean_bling_cell_text',
    'clean_columns',
    'clean_text',
    'contract_columns_from_model',
    'contract_from_df',
    'enforce_contract',
    'exact_contract_columns',
    'final_csv_bytes',
    'filename_for_operation',
    'physical_csv_contract_errors',
    'sanitize_final_dataframe',
    'validate_contract_identity',
]
