from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.universal.model_detector import ModelDetection, detect_model_type


@dataclass(frozen=True)
class UniversalContract:
    columns: list[str]
    model_type: str
    confidence: float
    reason: str
    preserve_order: bool = True
    allow_extra_columns: bool = False


def build_universal_contract(df_model: pd.DataFrame | None) -> UniversalContract:
    detection: ModelDetection = detect_model_type(df_model)
    return UniversalContract(
        columns=detection.columns,
        model_type=detection.model_type,
        confidence=detection.confidence,
        reason=detection.reason,
        preserve_order=True,
        allow_extra_columns=False,
    )


def validate_universal_output(df_output: pd.DataFrame, contract: UniversalContract) -> list[str]:
    errors: list[str] = []
    if not isinstance(df_output, pd.DataFrame):
        return ['Saída universal inválida.']
    output_columns = [str(column) for column in df_output.columns]
    if output_columns != contract.columns:
        errors.append('A planilha final não está idêntica ao modelo de destino em colunas e ordem.')
    extra = [column for column in output_columns if column not in contract.columns]
    missing = [column for column in contract.columns if column not in output_columns]
    if extra:
        errors.append('Colunas extras não permitidas: ' + ', '.join(extra))
    if missing:
        errors.append('Colunas ausentes: ' + ', '.join(missing))
    return errors


__all__ = ['UniversalContract', 'build_universal_contract', 'validate_universal_output']
