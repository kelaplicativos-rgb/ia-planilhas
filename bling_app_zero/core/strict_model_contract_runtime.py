from __future__ import annotations

from io import StringIO
from typing import Sequence
import csv

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.universal.internal_columns import is_generated_internal_column

RESPONSIBLE_FILE = 'bling_app_zero/core/strict_model_contract_runtime.py'
PATCH_ATTR = '_mapeiaai_strict_model_contract_runtime_v1'
INTERNAL_PREFIXES = ('_v2_',)
DEFAULT_SEPARATOR = ';'
DEFAULT_ENCODING = 'utf-8-sig'


def _audit(event: str, **details: object) -> None:
    try:
        add_audit_event(event, area='CONTRATO_MODELO', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _as_list(values: Sequence[object] | None) -> list[object]:
    if values is None:
        return []
    try:
        return list(values)
    except TypeError:
        return [values]


def _clean_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return text.strip()


def _is_internal(column: object) -> bool:
    text = str(column or '')
    return is_generated_internal_column(column) or any(text.startswith(prefix) for prefix in INTERNAL_PREFIXES)


def _strict_columns(columns: Sequence[object] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for column in _as_list(columns):
        if _is_internal(column):
            continue
        name = _clean_text(column)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _drop_internal(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    internal = [column for column in df.columns if _is_internal(column)]
    return df.drop(columns=internal, errors='ignore') if internal else df


def _normalize_df(df: pd.DataFrame | None, *, preserve_columns: bool) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = _drop_internal(df.copy().fillna(''))
    if not preserve_columns:
        out.columns = [_clean_text(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].map(_clean_text)
    return out.fillna('')


def _contract_from_df(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> list[str]:
    explicit = _strict_columns(contract_columns)
    if explicit:
        return explicit
    if isinstance(df, pd.DataFrame):
        return _strict_columns(df.columns)
    return []


def _enforce_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    contract = _contract_from_df(None, contract_columns)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=contract)
    out = _normalize_df(df, preserve_columns=bool(contract))
    if not contract:
        return out
    return out.reindex(columns=contract, fill_value='').fillna('')


def _force_empty_columns(df: pd.DataFrame, columns: Sequence[object] | None = None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in _strict_columns(columns):
        if column in out.columns:
            out[column] = ''
    return out


def _sanitize_final_dataframe(
    df: pd.DataFrame | None,
    *,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
    run_download_features: bool = True,
) -> pd.DataFrame:
    from bling_app_zero.core import final_csv_exporter as exporter

    contract = _contract_from_df(df, contract_columns)
    safe = _normalize_df(df, preserve_columns=bool(contract)) if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=contract)
    if run_download_features:
        safe = exporter.normalize_image_columns(safe)
    safe = _force_empty_columns(safe, explicit_empty_columns)
    return _enforce_contract(safe, contract)


def _validate_contract_identity(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> list[str]:
    contract = _contract_from_df(None, contract_columns)
    if not contract:
        return []
    if not isinstance(df, pd.DataFrame):
        return ['A planilha final não é uma tabela válida.']
    raw_internal = [str(column) for column in df.columns if _is_internal(column)]
    if raw_internal:
        return ['Colunas internas proibidas no arquivo final: ' + ', '.join(raw_internal)]
    output_columns = _strict_columns(df.columns)
    if output_columns != contract:
        return ['A planilha final não está fiel ao contrato de colunas do modelo anexado.']
    return []


def _to_csv_bytes_strict(df: pd.DataFrame, *, sep: str = DEFAULT_SEPARATOR) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, sep=sep, index=False, encoding=DEFAULT_ENCODING, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    return buffer.getvalue().encode(DEFAULT_ENCODING)


def _final_csv_bytes(
    df: pd.DataFrame | None,
    *,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
    sep: str = DEFAULT_SEPARATOR,
    run_download_features: bool = True,
) -> bytes:
    safe = _sanitize_final_dataframe(
        df,
        operation=operation,
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=run_download_features,
    )
    return _to_csv_bytes_strict(safe, sep=sep)


def install_strict_model_contract_runtime() -> bool:
    from bling_app_zero.core import final_csv_exporter as exporter
    from bling_app_zero.core import final_output_engine as engine

    if getattr(exporter, PATCH_ATTR, False):
        return False

    exporter.exact_contract_columns = _strict_columns
    exporter.clean_columns = _strict_columns
    exporter.contract_columns_from_model = lambda df_model: _strict_columns(getattr(df_model, 'columns', None)) if isinstance(df_model, pd.DataFrame) else []
    exporter.clean_explicit_empty_columns = lambda columns=None: set(_strict_columns(columns))
    exporter.drop_internal_columns = lambda df, prefixes=INTERNAL_PREFIXES: _drop_internal(df)
    exporter.enforce_contract = _enforce_contract
    exporter.contract_from_df = _contract_from_df
    exporter.sanitize_final_dataframe = _sanitize_final_dataframe
    exporter.validate_contract_identity = _validate_contract_identity
    exporter.final_csv_bytes = _final_csv_bytes

    engine.contract_columns_from_model = exporter.contract_columns_from_model
    engine.sanitize_final_dataframe = _sanitize_final_dataframe
    engine.validate_contract_identity = _validate_contract_identity
    engine.final_csv_bytes = _final_csv_bytes

    try:
        from bling_app_zero.ui import shared_final_csv as shared
        shared.contract_columns_from_model = exporter.contract_columns_from_model
    except Exception:
        pass

    setattr(exporter, PATCH_ATTR, True)
    _audit('strict_model_contract_runtime_installed', drops_generated_internal_columns=True, final_output_columns_must_match_model=True, prohibited_columns=['Arquivo origem', 'Página origem'])
    return True


__all__ = ['install_strict_model_contract_runtime']
