from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.exporter import enforce_export_contract
from bling_app_zero.core.final_csv_exporter import exact_contract_columns
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/ui/download_estoque_runtime_fix.py'
_PATCH_ATTR = '_download_estoque_runtime_fix_v2_exact_model'
_ORIGINAL_MISMATCH_ATTR = '_download_estoque_original_mismatch_error'
_ORIGINAL_CONTRACT_ATTR = '_download_estoque_original_dataframe_for_contract'

ESTOQUE_QTY_TERMS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'balanço')
ESTOQUE_DEPOSIT_TERMS = ('deposito', 'depósito')
ESTOQUE_CODE_TERMS = ('codigo', 'código', 'sku', 'referencia', 'referência', 'id', 'id produto', 'id_produto')

SESSION_MODEL_KEYS_BY_OPERATION = {
    'estoque': (
        'home_modelo_estoque_df',
        'df_modelo_estoque',
        'modelo_estoque_df',
        'estoque_wizard_df_modelo',
        'mapeiaai_final_contract_df',
    ),
    'cadastro': (
        'home_modelo_cadastro_df',
        'df_modelo_cadastro',
        'modelo_cadastro_df',
        'mapeiaai_final_contract_df',
    ),
    'atualizacao_preco': (
        'home_modelo_atualizacao_preco_df',
        'df_modelo_atualizacao_preco',
        'modelo_atualizacao_preco_df',
        'mapeiaai_final_contract_df',
    ),
    'universal': (
        'home_modelo_universal_df',
        'df_modelo_universal',
        'modelo_universal_df',
        'mapeiaai_final_contract_df',
    ),
}


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


def _session_model_columns(operation: str) -> tuple[list[str], str]:
    op = normalize_operation(operation)
    keys = SESSION_MODEL_KEYS_BY_OPERATION.get(op, ()) + SESSION_MODEL_KEYS_BY_OPERATION.get('universal', ())
    for key in keys:
        df_model = st.session_state.get(key)
        columns = exact_contract_columns(df_model.columns) if isinstance(df_model, pd.DataFrame) and len(df_model.columns) > 0 else []
        if columns:
            return columns, key
    return [], ''


def _adapt_to_exact_model(df: pd.DataFrame, contract_columns: list[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=contract_columns)
    source = df.copy().fillna('')
    normalized_to_original: dict[str, str] = {}
    for column in source.columns:
        key = normalize_key(column)
        if key and key not in normalized_to_original:
            normalized_to_original[key] = column

    out = pd.DataFrame(index=source.index)
    for target in contract_columns:
        if target in source.columns:
            out[target] = source[target]
            continue
        source_column = normalized_to_original.get(normalize_key(target))
        if source_column and source_column in source.columns:
            out[target] = source[source_column]
        else:
            out[target] = ''
    return enforce_export_contract(out, contract_columns).fillna('')


def install_download_estoque_runtime_fix() -> bool:
    try:
        from bling_app_zero.ui import home_download
    except Exception as exc:
        add_audit_event(
            'download_estoque_runtime_fix_import_failed',
            area='DOWNLOAD',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False

    if getattr(home_download, _PATCH_ATTR, False):
        return False

    original_mismatch = getattr(home_download, _ORIGINAL_MISMATCH_ATTR, None)
    if original_mismatch is None:
        original_mismatch = home_download._operation_contract_mismatch_error
        setattr(home_download, _ORIGINAL_MISMATCH_ATTR, original_mismatch)

    original_contract = getattr(home_download, _ORIGINAL_CONTRACT_ATTR, None)
    if original_contract is None:
        original_contract = home_download.download_dataframe_for_contract
        setattr(home_download, _ORIGINAL_CONTRACT_ATTR, original_contract)

    def guarded_dataframe_for_contract(df: pd.DataFrame, operation: str):
        op = normalize_operation(operation)
        contract_columns, source_key = _session_model_columns(op)
        if contract_columns:
            adapted = _adapt_to_exact_model(df, contract_columns)
            add_audit_event(
                'download_exact_uploaded_model_contract_applied',
                area='DOWNLOAD',
                status='OK',
                details={
                    'operation': op,
                    'source_key': source_key,
                    'columns_count': len(contract_columns),
                    'columns': contract_columns,
                    'reason': 'Download final deve ser exatamente igual ao modelo anexado.',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return adapted, True, contract_columns
        return original_contract(df, operation)

    def guarded_contract_mismatch(raw_df: pd.DataFrame, download_df: pd.DataFrame, operation: str) -> str:
        op = normalize_operation(operation)
        if op == OP_ESTOQUE and _looks_like_real_stock_download(download_df):
            add_audit_event(
                'download_estoque_contract_guard_released',
                area='DOWNLOAD',
                status='OK',
                details={
                    'operation': op,
                    'columns': [str(column) for column in getattr(download_df, 'columns', [])],
                    'reason': 'Contrato de estoque com quantidade e identificador/deposito nao deve ser bloqueado como cadastro.',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return ''
        return original_mismatch(raw_df, download_df, operation)

    home_download.download_dataframe_for_contract = guarded_dataframe_for_contract
    home_download._operation_contract_mismatch_error = guarded_contract_mismatch
    setattr(home_download, _PATCH_ATTR, True)
    add_audit_event(
        'download_exact_uploaded_model_runtime_fix_installed',
        area='DOWNLOAD',
        status='OK',
        details={'target': 'home_download.download_dataframe_for_contract', 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


__all__ = ['install_download_estoque_runtime_fix']
