from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.ai.ai_text_rules import clean_title_to_limit, is_description_column, is_title_column
from bling_app_zero.core.final_csv_exporter import (
    contract_columns_from_model,
    final_csv_bytes,
    sanitize_final_dataframe,
    validate_contract_identity,
)
from bling_app_zero.core.final_output_state import STATUS_DONE, STATUS_ERROR, FinalOutputRequest, FinalOutputResult, FinalOutputState
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import build_universal_contract, validate_universal_output

RESPONSIBLE_FILE = 'bling_app_zero/core/final_output_engine.py'


@dataclass(frozen=True)
class FinalOutputCommandResult:
    state: FinalOutputState
    output: pd.DataFrame | None = None
    csv_bytes: bytes = b''
    smartcore_result: Any = None
    errors: tuple[str, ...] = ()


def apply_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    out = output.copy().fillna('')
    for column in out.columns:
        if is_title_column(column):
            out[column] = out[column].map(clean_title_to_limit)
        elif is_description_column(column):
            out[column] = out[column].map(lambda value: re.sub(r'\s+', ' ', str(value or '').strip()))
    return out


def build_final_dataframe(source: pd.DataFrame, contract: pd.DataFrame, mapping: Mapping[str, str], *, apply_rules: bool = False) -> pd.DataFrame:
    """Monta o modelo anexado preenchido por linhas da origem.

    A regra deste fluxo é universal: o modelo anexado define somente colunas e
    ordem; os valores finais vêm da origem mapeada ou de valores fixos/manuais.
    Nenhuma linha de exemplo/instrução do modelo é copiada para o resultado.
    """
    if not isinstance(source, pd.DataFrame) or source.empty:
        output = empty_universal_output(contract, rows=0)
    else:
        output = build_universal_output(source, contract, dict(mapping or {}))
    if apply_rules:
        output = apply_text_rules(output)
    return output


def build_final_output(
    source: pd.DataFrame,
    contract: pd.DataFrame,
    mapping: Mapping[str, str],
    *,
    operation: str = 'universal',
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv',
    run_smart_features: bool = True,
) -> FinalOutputCommandResult:
    contract_columns = tuple(contract_columns_from_model(contract))
    request = FinalOutputRequest(operation=operation, file_name=file_name, contract_columns=contract_columns)
    contract_obj = build_universal_contract(contract)

    # Saída universal fiel: por padrão, não reescreve dados mapeados com IA/regras.
    # O objetivo é devolver o modelo anexado preenchido com os dados da origem.
    output = build_final_dataframe(source, contract, mapping, apply_rules=False)

    errors = tuple(str(item) for item in validate_universal_output(output, contract_obj) or ())
    if errors:
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=errors, message='Saída final bloqueada por erro de contrato.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', errors=errors)

    smartcore_result = None
    output = sanitize_final_dataframe(output, operation=operation, contract_columns=list(contract_columns), run_download_features=False)

    identity_errors = tuple(str(item) for item in validate_contract_identity(output, list(contract_columns)) or ())
    if identity_errors:
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=identity_errors, message='Saída final bloqueada por divergência de colunas.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', smartcore_result=smartcore_result, errors=identity_errors)

    try:
        csv_data = final_csv_bytes(output, operation=operation, contract_columns=list(contract_columns), run_download_features=False)
    except Exception as exc:
        csv_error = (str(exc),)
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=csv_error, message='Saída final bloqueada por erro físico de CSV.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', smartcore_result=smartcore_result, errors=csv_error)

    result = FinalOutputResult(
        status=STATUS_DONE,
        rows=int(len(output)),
        columns=tuple(str(column) for column in output.columns),
        file_name=file_name,
        csv_size_bytes=len(csv_data),
        smartcore_score=0,
        message='Modelo anexado preenchido com dados da origem.',
        warnings=tuple(),
    )
    return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=output, csv_bytes=csv_data, smartcore_result=smartcore_result)


def build_final_output_report(result: FinalOutputCommandResult) -> dict[str, Any]:
    return {
        'request': result.state.request.to_dict(),
        'result': result.state.result.to_dict(),
        'ok': result.state.result.ok,
    }


__all__ = [
    'FinalOutputCommandResult',
    'apply_text_rules',
    'build_final_dataframe',
    'build_final_output',
    'build_final_output_report',
]
