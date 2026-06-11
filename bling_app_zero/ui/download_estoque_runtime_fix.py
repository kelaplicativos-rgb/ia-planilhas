from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/ui/download_estoque_runtime_fix.py'
_PATCH_ATTR = '_download_estoque_runtime_fix_v5_template_file'
_ORIGINAL_ATTR = '_download_estoque_original_mismatch_error'

ESTOQUE_QTY_TERMS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'balanço')
ESTOQUE_DEPOSIT_TERMS = ('deposito', 'depósito')
ESTOQUE_CODE_TERMS = ('codigo', 'código', 'sku', 'referencia', 'referência', 'id', 'id produto', 'id_produto')


def _columns(df: Any) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    return [normalize_key(column) for column in df.columns]


def _has_term(columns: list[str], terms: tuple[str, ...]) -> bool:
    normalized_terms = [normalize_key(term) for term in terms]
    return any(any(term in column for term in normalized_terms) for column in columns)


def _looks_like_real_stock_download(df: Any) -> bool:
    columns = _columns(df)
    if not columns:
        return False
    has_quantity = _has_term(columns, ESTOQUE_QTY_TERMS)
    has_identifier = _has_term(columns, ESTOQUE_CODE_TERMS)
    has_deposit = _has_term(columns, ESTOQUE_DEPOSIT_TERMS)
    return bool(has_quantity and (has_identifier or has_deposit))


def install_download_estoque_runtime_fix() -> bool:
    try:
        from bling_app_zero.ui.exact_model_download_runtime import install_exact_model_download_runtime
        install_exact_model_download_runtime()
    except Exception as exc:
        add_audit_event('download_exact_model_runtime_install_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    try:
        from bling_app_zero.ui.exact_template_file_runtime import install_exact_template_file_runtime
        install_exact_template_file_runtime()
    except Exception as exc:
        add_audit_event('download_exact_template_runtime_install_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    try:
        from bling_app_zero.ui import home_download
    except Exception as exc:
        add_audit_event('download_estoque_runtime_fix_import_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    if getattr(home_download, _PATCH_ATTR, False):
        return False

    original = getattr(home_download, _ORIGINAL_ATTR, None)
    if original is None:
        original = home_download._operation_contract_mismatch_error
        setattr(home_download, _ORIGINAL_ATTR, original)

    def guarded_contract_mismatch(raw_df: pd.DataFrame, download_df: pd.DataFrame, operation: str) -> str:
        op = normalize_operation(operation)
        if op == OP_ESTOQUE and _looks_like_real_stock_download(download_df):
            add_audit_event('download_estoque_contract_guard_released', area='DOWNLOAD', status='OK', details={'operation': op, 'columns': [str(column) for column in getattr(download_df, 'columns', [])], 'responsible_file': RESPONSIBLE_FILE})
            return ''
        return original(raw_df, download_df, operation)

    home_download._operation_contract_mismatch_error = guarded_contract_mismatch
    setattr(home_download, _PATCH_ATTR, True)
    add_audit_event('download_estoque_runtime_fix_installed', area='DOWNLOAD', status='OK', details={'exact_model_runtime': True, 'exact_template_file_runtime': True, 'responsible_file': RESPONSIBLE_FILE})
    return True


__all__ = ['install_download_estoque_runtime_fix']
