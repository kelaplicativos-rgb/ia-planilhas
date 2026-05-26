from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

import pandas as pd

from bling_app_zero.core.final_download_resources import normalize_image_urls

try:
    from bling_app_zero.features.runtime import run_features_for_stage
except Exception:  # pragma: no cover
    run_features_for_stage = None

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
    """Converte sequências em lista sem avaliar truth value de pandas.Index."""
    if values is None:
        return []
    try:
        return list(values)
    except TypeError:
        return [values]


def clean_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '')
    text = text.replace('\x00', '')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def clean_columns(columns: Sequence[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for column in _as_list(columns):
        text = clean_text(column)
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def exact_contract_columns(columns: Sequence[object] | None) -> list[str]:
    """Preserva o contrato do modelo anexado na ordem exata recebida.

    BLINGFIX contrato bytes:
    - o download final não deve criar, remover nem reordenar colunas;
    - quando o fluxo fornece colunas do modelo anexado, elas são a fonte da verdade;
    - não aplicamos deduplicação nem normalização agressiva no cabeçalho explícito,
      porque o contrato precisa acompanhar o modelo usado pelo usuário.
    """
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


def normalize_dataframe(df: pd.DataFrame | None, *, keep_internal: bool = False) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna('')
    if not keep_internal:
        out = drop_internal_columns(out)
    out.columns = [clean_text(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].map(clean_text)
    return out.fillna('')


def contract_from_df(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> list[str]:
    explicit = exact_contract_columns(contract_columns)
    if explicit:
        return explicit
    if isinstance(df, pd.DataFrame):
        return clean_columns(df.columns)
    return []


def force_empty_columns(df: pd.DataFrame, columns: Sequence[object] | None = None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    protected = clean_explicit_empty_columns(columns)
    for column in protected:
        if column in out.columns:
            out[column] = ''
    return out


def enforce_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    columns = contract_from_df(None, contract_columns)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    out = normalize_dataframe(df, keep_internal=False)
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
    errors: list[str] = []
    if output_columns != contract:
        errors.append('A planilha final não está byte-a-byte fiel ao contrato de colunas do modelo anexado.')
    missing = [column for column in contract if column not in output_columns]
    extra = [column for column in output_columns if column not in contract]
    if missing:
        errors.append('Colunas ausentes no download final: ' + ', '.join(missing))
    if extra:
        errors.append('Colunas extras no download final: ' + ', '.join(extra))
    return errors


def sanitize_final_dataframe(
    df: pd.DataFrame | None,
    *,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
    run_download_features: bool = True,
) -> pd.DataFrame:
    """Blindagem única antes do CSV final dos fluxos Bling.

    Quando `contract_columns` é informado, esse contrato vem do modelo usado no
    fluxo e passa a mandar no download final: mesmas colunas, mesma ordem e sem
    colunas extras. As features de download podem limpar valores, mas ao final o
    contrato é reaplicado obrigatoriamente.
    """
    if df is None:
        return enforce_contract(None, contract_columns)

    input_df = normalize_dataframe(df, keep_internal=False)
    contract = contract_from_df(input_df, contract_columns)
    protected_empty = clean_explicit_empty_columns(explicit_empty_columns)
    input_df = force_empty_columns(input_df, protected_empty)

    safe = input_df
    if run_download_features and callable(run_features_for_stage):
        context = run_features_for_stage(
            operation=str(operation or 'global').strip().lower() or 'global',
            stage='download',
            final_df=input_df.copy().fillna(''),
            config={
                'contract_columns': list(contract),
                'explicit_empty_columns': sorted(protected_empty),
            },
        )
        safe = context.final_df if isinstance(getattr(context, 'final_df', None), pd.DataFrame) else input_df

    safe = force_empty_columns(normalize_dataframe(safe, keep_internal=False), protected_empty)
    return enforce_contract(safe, contract)


def final_csv_bytes(
    df: pd.DataFrame | None,
    *,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
    sep: str = DEFAULT_SEPARATOR,
    run_download_features: bool = True,
) -> bytes:
    safe = sanitize_final_dataframe(
        df,
        operation=operation,
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=run_download_features,
    )
    buffer = BytesIO()
    safe.to_csv(buffer, sep=sep, index=False, encoding=DEFAULT_ENCODING)
    return buffer.getvalue()


def filename_for_operation(operation: str) -> str:
    op = str(operation or 'bling').lower().strip()
    if op == 'estoque':
        return 'bling_atualizacao_estoque.csv'
    if op == 'cadastro':
        return 'bling_cadastro_produtos.csv'
    if op in {'precos_multiloja', 'preco_multiloja', 'multiloja', 'preco'}:
        return 'bling_precos_multilojas.csv'
    return 'bling_exportacao.csv'


def build_final_csv_export(
    df: pd.DataFrame | None,
    *,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
    file_name: str | None = None,
    sep: str = DEFAULT_SEPARATOR,
    run_download_features: bool = True,
) -> FinalCsvExportResult:
    safe = sanitize_final_dataframe(
        df,
        operation=operation,
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=run_download_features,
    )
    buffer = BytesIO()
    safe.to_csv(buffer, sep=sep, index=False, encoding=DEFAULT_ENCODING)
    filename = file_name or filename_for_operation(operation)
    return FinalCsvExportResult(
        df=safe,
        csv_bytes=buffer.getvalue(),
        filename=filename,
        operation=str(operation or 'global'),
        columns=tuple(map(str, safe.columns)),
        rows=len(safe),
    )


__all__ = [
    'DEFAULT_ENCODING',
    'DEFAULT_SEPARATOR',
    'FinalCsvExportResult',
    'INTERNAL_COLUMN_PREFIXES',
    'RESPONSIBLE_FILE',
    'build_final_csv_export',
    'clean_columns',
    'clean_explicit_empty_columns',
    'clean_text',
    'contract_columns_from_model',
    'contract_from_df',
    'drop_internal_columns',
    'enforce_contract',
    'exact_contract_columns',
    'filename_for_operation',
    'final_csv_bytes',
    'force_empty_columns',
    'normalize_dataframe',
    'normalize_image_urls',
    'sanitize_final_dataframe',
    'validate_contract_identity',
]
