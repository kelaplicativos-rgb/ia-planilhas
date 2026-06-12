from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.agents.blingsmartcore import apply_blingsmartcore
from bling_app_zero.agents.site_ai_validator import SmartScanQuality
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.exporter import enforce_export_contract
from bling_app_zero.core.operation_contract import normalize_operation
from bling_app_zero.universal.contract_adapter import adapt_dataframe_to_model_contract, model_for_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/unified_origin_contract.py'


@dataclass(frozen=True)
class UnifiedOriginContractResult:
    origin: str
    operation: str
    rows_before: int
    rows_after_smartcore: int
    rows_after_contract: int
    contract_applied: bool
    contract_source: str
    contract_columns: list[str]
    quality: SmartScanQuality


def _clean_columns(columns: Iterable[object] | None) -> list[str]:
    return [str(column).replace('\ufeff', '').replace('\r', ' ').replace('\n', ' ').strip() for column in (columns or []) if str(column).strip()]


def _origin_text(origin: str | None) -> str:
    text = str(origin or '').strip().lower()
    return text or 'desconhecida'


def apply_unified_origin_contract(
    df: pd.DataFrame,
    *,
    operation: str,
    origin: str = 'desconhecida',
    uploaded_columns: Iterable[object] | None = None,
) -> tuple[pd.DataFrame, UnifiedOriginContractResult]:
    """Normaliza qualquer origem e aplica o mesmo contrato antes de download/API.

    Arquivo, site, XML, PDF, tabela colada e API publica entram por caminhos
    diferentes, mas daqui para frente todos seguem a mesma saida do Bling.
    """
    op = normalize_operation(operation)
    source = _origin_text(origin)
    raw = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    rows_before = int(len(raw))

    smart_df, smart_result = apply_blingsmartcore(raw, origin=source, operation=op)
    contract_columns = _clean_columns(uploaded_columns)
    contract_source = 'uploaded_model' if contract_columns else 'internal_model'

    if contract_columns:
        final_df = enforce_export_contract(smart_df, contract_columns)
        contract_applied = True
    else:
        model = model_for_operation(op)
        final_df = adapt_dataframe_to_model_contract(smart_df, model)
        contract_applied = isinstance(model, pd.DataFrame) and len(model.columns) > 0
        contract_columns = [str(column) for column in model.columns] if contract_applied else []

    result = UnifiedOriginContractResult(
        origin=source,
        operation=op,
        rows_before=rows_before,
        rows_after_smartcore=int(len(smart_df)) if isinstance(smart_df, pd.DataFrame) else 0,
        rows_after_contract=int(len(final_df)) if isinstance(final_df, pd.DataFrame) else 0,
        contract_applied=bool(contract_applied),
        contract_source=contract_source,
        contract_columns=contract_columns,
        quality=smart_result.quality,
    )
    add_audit_event(
        'unified_origin_contract_applied',
        area='CONTRATO_UNICO',
        status='OK' if result.rows_after_contract else 'AVISO',
        details={
            'origin': result.origin,
            'operation': result.operation,
            'rows_before': result.rows_before,
            'rows_after_smartcore': result.rows_after_smartcore,
            'rows_after_contract': result.rows_after_contract,
            'contract_applied': result.contract_applied,
            'contract_source': result.contract_source,
            'contract_columns': len(result.contract_columns),
            'quality': asdict(result.quality),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return final_df.fillna('') if isinstance(final_df, pd.DataFrame) else pd.DataFrame(), result


__all__ = ['UnifiedOriginContractResult', 'apply_unified_origin_contract']
