from __future__ import annotations

import importlib
import re
from collections.abc import MutableMapping
from typing import Any

import pandas as pd

from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'
_FALLBACK_STATE: dict[str, Any] = {}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e')
    text = text.replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _is_bling_internal_id_column(column: object) -> bool:
    """Identifica somente colunas de ID interno do Bling.

    Essa coluna não deve receber ID de site, GTIN, SKU nem código do fornecedor.
    Ela só poderia ser preenchida quando já vier do próprio Bling; por regra de
    saída do sistema ela nasce vazia para evitar atualização errada por API/CSV.
    """
    normalized = _normalize_column_name(column)
    return normalized in {
        'id',
        'id produto',
        'id produto bling',
        'id bling',
        'codigo bling',
        'código bling',
    }


def _clear_bling_internal_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    out = df.copy().fillna('')
    for column in out.columns:
        if _is_bling_internal_id_column(column):
            out[column] = ''
    return out


def adapt_dataframe_to_model_contract(df: pd.DataFrame, df_model: pd.DataFrame | None) -> pd.DataFrame:
    """Adapta a saída final para ficar fiel ao modelo anexado."""
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if not isinstance(df_model, pd.DataFrame) or not len(df_model.columns):
        return _clear_bling_internal_id_columns(df.copy()).reset_index(drop=True)

    out = _clear_bling_internal_id_columns(df.copy().fillna(''))
    contract_columns = [str(column) for column in df_model.columns]
    adapted = pd.DataFrame(index=out.index)
    for column in contract_columns:
        if _is_bling_internal_id_column(column):
            adapted[column] = ''
        elif column in out.columns:
            adapted[column] = out[column].fillna('').astype(str)
        else:
            adapted[column] = ''
    return adapted.reset_index(drop=True)


def _first_valid_model_from_session(candidate_keys: list[str], *, state: MutableMapping[str, Any] | None = None) -> pd.DataFrame | None:
    store = state_store(state)
    for key in candidate_keys:
        value = store.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns):
            return value.copy().fillna('')
    return None


def _entry_context(*, state: MutableMapping[str, Any] | None = None) -> str:
    store = state_store(state)
    value = str(store.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value == 'bling':
        return CONTEXT_BLING_API
    if value in {CONTEXT_BLING_API, CONTEXT_BLING_CSV, CONTEXT_UNIVERSAL}:
        return value
    return ''


def _resolved_operation(operation: str, *, state: MutableMapping[str, Any] | None = None) -> str:
    store = state_store(state)
    op = normalize_contract_operation(operation)
    if op:
        return op
    detected = normalize_contract_operation(store.get(MODEL_CONTRACT_TYPE_KEY))
    return detected or 'universal'


def _universal_model_keys() -> list[str]:
    return [
        'home_modelo_universal_df',
        'df_modelo_universal',
        'modelo_universal_df',
        'mapeiaai_universal_model_df',
        'cadastro_wizard_df_modelo',
    ]


def _bling_cadastro_model_keys() -> list[str]:
    return [
        'home_modelo_cadastro_df',
        'df_modelo_cadastro',
        'modelo_cadastro_df',
        'cadastro_wizard_df_modelo',
    ]


def _bling_estoque_model_keys() -> list[str]:
    return [
        'home_modelo_estoque_df',
        'df_modelo_estoque',
        'modelo_estoque_df',
        'cadastro_wizard_df_modelo_estoque',
        'estoque_wizard_df_modelo',
    ]


def _bling_preco_model_keys() -> list[str]:
    return [
        'home_modelo_atualizacao_preco_df',
        'df_modelo_atualizacao_preco',
        'modelo_atualizacao_preco_df',
        'cadastro_wizard_df_modelo',
    ]


def _bling_model_keys_for_operation(op: str) -> list[str]:
    if op == 'estoque':
        return _bling_estoque_model_keys()
    if op == 'atualizacao_preco':
        return _bling_preco_model_keys()
    if op == 'cadastro':
        return _bling_cadastro_model_keys()
    return _bling_cadastro_model_keys() + _bling_estoque_model_keys() + _bling_preco_model_keys()


def model_for_operation(operation: str, *, state: MutableMapping[str, Any] | None = None) -> pd.DataFrame | None:
    """Busca modelo salvo na sessão respeitando o caminho da Home."""
    context = _entry_context(state=state)
    op = _resolved_operation(operation, state=state)

    if context == CONTEXT_BLING_API:
        return None

    if context == CONTEXT_UNIVERSAL:
        return _first_valid_model_from_session(_universal_model_keys(), state=state)

    if context == CONTEXT_BLING_CSV:
        return _first_valid_model_from_session(_bling_model_keys_for_operation(op), state=state)

    if op == 'universal':
        return _first_valid_model_from_session(_universal_model_keys(), state=state)
    return _first_valid_model_from_session(_bling_model_keys_for_operation(op), state=state)


__all__ = ['adapt_dataframe_to_model_contract', 'model_for_operation', 'state_store']
