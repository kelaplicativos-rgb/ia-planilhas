from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_wizard_state import (
    ESTOQUE_CONFIDENCE_KEY,
    ESTOQUE_FINAL_KEY,
    ESTOQUE_MAPPING_KEY,
    LEGACY_ESTOQUE_CONFIDENCE_KEY,
    LEGACY_ESTOQUE_FINAL_KEY,
    LEGACY_ESTOQUE_MAPPING_KEY,
)
from bling_app_zero.ui.flow_guard import render_flow_blocker
from bling_app_zero.ui.home_shared import df_signature

CADASTRO_SOURCE_SIGNATURE_KEY = 'cadastro_source_signature_atual'
CADASTRO_ORIGEM_KEY = 'cadastro_wizard_df_origem'
CADASTRO_ORIGEM_PRICED_KEY = 'cadastro_wizard_df_para_mapear'
CADASTRO_MODELO_KEY = 'cadastro_wizard_df_modelo'
CADASTRO_MODELO_ESTOQUE_KEY = 'cadastro_wizard_df_modelo_estoque'
CADASTRO_MAPPING_CONFIRMED_KEY = 'cadastro_mapping_confirmed'
CADASTRO_MAPPING_SIGNATURE_KEY = 'cadastro_mapping_confirmed_signature'
CADASTRO_EXPECTED_ROWS_KEY = 'cadastro_wizard_expected_source_rows'
CADASTRO_EXPECTED_SIGNATURE_KEY = 'cadastro_wizard_expected_source_signature'
CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY = 'cadastro_supplier_price_master_filter_active'
CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY = 'cadastro_supplier_price_master_rows'
CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY = 'cadastro_supplier_price_master_signature'
CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME = 'REGRA_FILTRO_MESTRE_FORNECEDOR_PRECOS'
UNIVERSAL_FINAL_KEY = 'df_final_universal'
LEGACY_CADASTRO_FINAL_KEY = 'df_final_cadastro'
BLING_IMPORTADOR_PRODUTOS_URL = 'https://www.bling.com.br/importador.produtos.php'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
CONTEXT_BLING_CSV = 'bling_csv'
CONTEXT_UNIVERSAL = 'universal'
SMARTSCAN_MANUAL_KEYS = (
    'blingsmartscan_manual_continue_required',
    'blingsmartscan_ready_to_continue',
)
CONTEXT_FINAL_KEYS = {
    CONTEXT_BLING_API: 'df_final_bling_api',
    CONTEXT_BLING_CSV: 'df_final_bling_csv',
    CONTEXT_UNIVERSAL: UNIVERSAL_FINAL_KEY,
}
CONTEXT_MAPPING_KEYS = {
    CONTEXT_BLING_API: 'mapping_bling_api',
    CONTEXT_BLING_CSV: 'mapping_bling_csv',
    CONTEXT_UNIVERSAL: 'mapping_universal',
}
CONTEXT_CONFIDENCE_KEYS = {
    CONTEXT_BLING_API: 'mapping_confidence_bling_api',
    CONTEXT_BLING_CSV: 'mapping_confidence_bling_csv',
    CONTEXT_UNIVERSAL: 'mapping_confidence_universal',
}

CADASTRO_STOCK_OUTPUT_KEYS = [
    ESTOQUE_FINAL_KEY,
    ESTOQUE_MAPPING_KEY,
    ESTOQUE_CONFIDENCE_KEY,
    LEGACY_ESTOQUE_FINAL_KEY,
    LEGACY_ESTOQUE_MAPPING_KEY,
    LEGACY_ESTOQUE_CONFIDENCE_KEY,
]

CADASTRO_OUTPUT_KEYS = [
    UNIVERSAL_FINAL_KEY,
    LEGACY_CADASTRO_FINAL_KEY,
    'df_final_bling_api',
    'df_final_bling_csv',
    'mapping_bling_api',
    'mapping_bling_csv',
    'mapping_universal',
    'mapping_confidence_bling_api',
    'mapping_confidence_bling_csv',
    'mapping_confidence_universal',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
    'df_origem_cadastro_precificada',
    *CADASTRO_STOCK_OUTPUT_KEYS,
    CADASTRO_ORIGEM_PRICED_KEY,
    CADASTRO_MAPPING_CONFIRMED_KEY,
    CADASTRO_MAPPING_SIGNATURE_KEY,
]


def _entry_context() -> str:
    value = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if value in CONTEXT_FINAL_KEYS:
        return value
    return CONTEXT_UNIVERSAL


def _is_api_context() -> bool:
    return _entry_context() == CONTEXT_BLING_API


def _context_final_key() -> str:
    return CONTEXT_FINAL_KEYS.get(_entry_context(), UNIVERSAL_FINAL_KEY)


def _context_mapping_key() -> str:
    return CONTEXT_MAPPING_KEYS.get(_entry_context(), 'mapping_universal')


def _smartscan_manual_continue_pending() -> bool:
    return any(bool(st.session_state.get(key)) for key in SMARTSCAN_MANUAL_KEYS)


def valid_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def get_universal_final_df() -> pd.DataFrame | None:
    current = st.session_state.get(UNIVERSAL_FINAL_KEY)
    if valid_df(current):
        return current
    legacy = st.session_state.get(LEGACY_CADASTRO_FINAL_KEY)
    if valid_df(legacy):
        st.session_state[UNIVERSAL_FINAL_KEY] = legacy
        return legacy
    return current if isinstance(current, pd.DataFrame) else None


def get_context_final_df() -> pd.DataFrame | None:
    key = _context_final_key()
    current = st.session_state.get(key)
    if valid_df(current):
        return current
    if key == UNIVERSAL_FINAL_KEY:
        return get_universal_final_df()
    legacy = st.session_state.get(LEGACY_CADASTRO_FINAL_KEY)
    if valid_df(legacy):
        return legacy
    return current if isinstance(current, pd.DataFrame) else None


def set_universal_final_df(df_final: pd.DataFrame | None) -> pd.DataFrame | None:
    if not isinstance(df_final, pd.DataFrame):
        return df_final
    fixed = df_final.copy()
    st.session_state[UNIVERSAL_FINAL_KEY] = fixed
    st.session_state[LEGACY_CADASTRO_FINAL_KEY] = fixed
    return fixed


def set_context_final_df(df_final: pd.DataFrame | None) -> pd.DataFrame | None:
    if not isinstance(df_final, pd.DataFrame):
        return df_final
    fixed = df_final.copy()
    st.session_state[_context_final_key()] = fixed
    st.session_state[LEGACY_CADASTRO_FINAL_KEY] = fixed
    if _entry_context() == CONTEXT_UNIVERSAL:
        st.session_state[UNIVERSAL_FINAL_KEY] = fixed
    return fixed


def is_site_origin() -> bool:
    return str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '').strip().lower() == 'site'


def _supplier_origin_label() -> str:
    return 'captura/origem do fornecedor' if is_site_origin() else 'planilha/origem do fornecedor'


def _supplier_origin_short_label() -> str:
    return 'origem do fornecedor' if is_site_origin() else 'planilha do fornecedor'


def supplier_price_master_filter_active() -> bool:
    return bool(st.session_state.get(CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY, False))


def activate_supplier_price_master_filter(df_origem: pd.DataFrame | None) -> None:
    if not valid_df(df_origem):
        st.session_state.pop(CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY, None)
        st.session_state.pop(CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY, None)
        st.session_state.pop(CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY, None)
        return
    st.session_state[CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY] = True
    st.session_state[CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY] = int(len(df_origem))
    st.session_state[CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY] = df_signature(df_origem)


def supplier_price_master_expected_rows() -> int:
    try:
        return int(st.session_state.get(CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY) or 0)
    except Exception:
        return 0


def enforce_supplier_price_master_filter(df_final: pd.DataFrame | None) -> pd.DataFrame | None:
    if not supplier_price_master_filter_active() or not isinstance(df_final, pd.DataFrame):
        return df_final
    expected = supplier_price_master_expected_rows()
    if expected <= 0:
        return df_final
    if len(df_final) > expected:
        fixed = df_final.iloc[:expected].copy()
        set_context_final_df(fixed)
        st.session_state['cadastro_supplier_price_master_excess_rows_removed'] = int(len(df_final) - expected)
        return fixed
    st.session_state.pop('cadastro_supplier_price_master_excess_rows_removed', None)
    return df_final


def render_supplier_price_master_notice(df_final: pd.DataFrame | None = None) -> None:
    if not supplier_price_master_filter_active():
        return
    expected = supplier_price_master_expected_rows()
    current = len(df_final) if isinstance(df_final, pd.DataFrame) else expected
    removed = int(st.session_state.get('cadastro_supplier_price_master_excess_rows_removed') or 0)
    source_label = _supplier_origin_label()
    short_label = _supplier_origin_short_label()
    st.warning(
        f'{CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME}: a {source_label} está sendo usada como filtro mestre. '
        f'O CSV final terá somente produtos presentes na {short_label}.'
    )
    st.caption(
        f'Produtos na {short_label}: {expected}. Produtos no resultado atual: {current}. '
        f'Produtos fora da {short_label} são desconsiderados.'
    )
    if removed > 0:
        st.caption(f'Blindagem aplicada: {removed} linha(s) excedente(s) foram removida(s) antes do preview/download.')


def enforce_cadastro_model_columns(df_final: pd.DataFrame | None = None) -> pd.DataFrame | None:
    if df_final is None:
        df_final = get_context_final_df()
    if _is_api_context():
        fixed = enforce_supplier_price_master_filter(df_final)
        if isinstance(fixed, pd.DataFrame):
            set_context_final_df(fixed)
        return fixed
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    if not isinstance(df_final, pd.DataFrame) or not valid_model(df_modelo):
        fixed = enforce_supplier_price_master_filter(df_final)
        if isinstance(fixed, pd.DataFrame):
            set_context_final_df(fixed)
        return fixed
    fixed = df_final.reindex(columns=list(df_modelo.columns), fill_value='')
    fixed = enforce_supplier_price_master_filter(fixed)
    if isinstance(fixed, pd.DataFrame):
        set_context_final_df(fixed)
    return fixed


def clear_cadastro_outputs() -> None:
    for key in CADASTRO_OUTPUT_KEYS:
        st.session_state.pop(key, None)


def clear_cadastro_outputs_if_source_changed(df_origem: pd.DataFrame | None) -> None:
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return
    signature = df_signature(df_origem)
    previous = st.session_state.get(CADASTRO_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    clear_cadastro_outputs()
    st.session_state[CADASTRO_SOURCE_SIGNATURE_KEY] = signature


def store_expected_source_rows(df_origem: pd.DataFrame | None) -> None:
    if not valid_df(df_origem):
        st.session_state.pop(CADASTRO_EXPECTED_ROWS_KEY, None)
        st.session_state.pop(CADASTRO_EXPECTED_SIGNATURE_KEY, None)
        return
    st.session_state[CADASTRO_EXPECTED_ROWS_KEY] = int(len(df_origem))
    st.session_state[CADASTRO_EXPECTED_SIGNATURE_KEY] = df_signature(df_origem)


def expected_source_rows() -> int:
    try:
        return int(st.session_state.get(CADASTRO_EXPECTED_ROWS_KEY) or 0)
    except Exception:
        return 0


def row_count_matches_source(df_final: pd.DataFrame | None) -> bool:
    df_final = enforce_supplier_price_master_filter(df_final)
    expected = expected_source_rows()
    if expected <= 0:
        return True
    return isinstance(df_final, pd.DataFrame) and len(df_final) == expected


def render_row_count_blocker(df_final: pd.DataFrame | None) -> bool:
    df_final = enforce_supplier_price_master_filter(df_final)
    expected = expected_source_rows()
    current = len(df_final) if isinstance(df_final, pd.DataFrame) else 0
    if expected <= 0 or current == expected:
        return False
    short_label = _supplier_origin_short_label()
    render_flow_blocker(
        f'A {short_label} tem {expected} produto(s), mas o arquivo final tem {current}. Volte para Entrada, confira a origem e refaça/confirme o mapeamento antes de baixar.',
        title='Proteção ativada',
        action_label='Download',
    )
    st.caption(
        'O sistema bloqueou o avanço para evitar perda silenciosa de produtos no CSV final. '
        f'Somente produtos listados na {short_label} podem ser gerados.'
    )
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    return True


def store_cadastro_context(
    df_origem: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> None:
    if valid_df(df_origem):
        st.session_state[CADASTRO_ORIGEM_KEY] = df_origem
        store_expected_source_rows(df_origem)
        activate_supplier_price_master_filter(df_origem)
    else:
        st.session_state.pop(CADASTRO_ORIGEM_KEY, None)
        store_expected_source_rows(None)
        activate_supplier_price_master_filter(None)
    if valid_model(df_modelo):
        st.session_state[CADASTRO_MODELO_KEY] = df_modelo
    else:
        st.session_state.pop(CADASTRO_MODELO_KEY, None)
    if valid_model(df_modelo_estoque):
        st.session_state[CADASTRO_MODELO_ESTOQUE_KEY] = df_modelo_estoque
    else:
        st.session_state.pop(CADASTRO_MODELO_ESTOQUE_KEY, None)


def cadastro_context_ready() -> bool:
    if _smartscan_manual_continue_pending():
        return False
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    return valid_df(df_origem) and valid_model(df_modelo)


def _api_direct_source_df() -> pd.DataFrame | None:
    for key in (CADASTRO_ORIGEM_PRICED_KEY, CADASTRO_ORIGEM_KEY, 'df_origem_planilha', 'df_site_bruto'):
        df = st.session_state.get(key)
        if valid_df(df):
            return df.copy().fillna('')
    return None


def ensure_api_direct_final_df() -> pd.DataFrame | None:
    if not _is_api_context():
        return get_context_final_df()
    current = get_context_final_df()
    if valid_df(current):
        return enforce_supplier_price_master_filter(current)
    source = _api_direct_source_df()
    if valid_df(source):
        st.session_state['mapping_bling_api'] = {str(column): str(column) for column in source.columns}
        st.session_state['mapping_confidence_bling_api'] = {str(column): 1.0 for column in source.columns}
        st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
        st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = df_signature(source)
        set_context_final_df(source)
        return enforce_supplier_price_master_filter(source)
    return None


def cadastro_mapping_ready() -> bool:
    if _is_api_context():
        df_final = ensure_api_direct_final_df()
        return valid_df(df_final) and row_count_matches_source(df_final)
    raw_final = get_context_final_df()
    df_final = enforce_cadastro_model_columns(raw_final)
    mapping = st.session_state.get(_context_mapping_key())
    if not isinstance(mapping, dict) or not mapping:
        mapping = st.session_state.get('mapping_cadastro')
    confirmed = bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY))
    return valid_df(df_final) and row_count_matches_source(df_final) and isinstance(mapping, dict) and bool(mapping) and confirmed


def get_cadastro_context() -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    return (
        st.session_state.get(CADASTRO_ORIGEM_KEY),
        st.session_state.get(CADASTRO_MODELO_KEY),
        st.session_state.get(CADASTRO_MODELO_ESTOQUE_KEY),
    )


def set_mapping_confirmed(mapping: dict, df_origem: pd.DataFrame | None) -> None:
    st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
    if isinstance(mapping, dict):
        st.session_state[_context_mapping_key()] = dict(mapping)
        st.session_state['mapping_cadastro'] = dict(mapping)
    if isinstance(df_origem, pd.DataFrame):
        signature = df_signature(df_origem)
        st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature


def mapping_confirmed_for(df_origem: pd.DataFrame | None) -> bool:
    if _smartscan_manual_continue_pending():
        return False
    if not bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY)):
        return False
    if not isinstance(df_origem, pd.DataFrame):
        return False
    return st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY) == df_signature(df_origem)


def get_context_mapping() -> dict:
    mapping = st.session_state.get(_context_mapping_key())
    if isinstance(mapping, dict):
        return mapping
    fallback = st.session_state.get('mapping_cadastro')
    return fallback if isinstance(fallback, dict) else {}


def get_context_confidence() -> dict:
    confidence = st.session_state.get(CONTEXT_CONFIDENCE_KEYS.get(_entry_context(), 'mapping_confidence_universal'))
    if isinstance(confidence, dict):
        return confidence
    fallback = st.session_state.get('mapping_confidence_cadastro')
    return fallback if isinstance(fallback, dict) else {}


def set_context_mapping(mapping: dict | None, confidence: dict | None = None) -> None:
    if isinstance(mapping, dict):
        st.session_state[_context_mapping_key()] = dict(mapping)
        st.session_state['mapping_cadastro'] = dict(mapping)
    if isinstance(confidence, dict):
        st.session_state[CONTEXT_CONFIDENCE_KEYS.get(_entry_context(), 'mapping_confidence_universal')] = dict(confidence)
        st.session_state['mapping_confidence_cadastro'] = dict(confidence)


def build_import_hint() -> str:
    return BLING_IMPORTADOR_PRODUTOS_URL


__all__ = [
    'BLING_IMPORTADOR_PRODUTOS_URL',
    'CADASTRO_EXPECTED_ROWS_KEY',
    'CADASTRO_EXPECTED_SIGNATURE_KEY',
    'CADASTRO_MAPPING_CONFIRMED_KEY',
    'CADASTRO_MAPPING_SIGNATURE_KEY',
    'CADASTRO_MODELO_ESTOQUE_KEY',
    'CADASTRO_MODELO_KEY',
    'CADASTRO_ORIGEM_KEY',
    'CADASTRO_ORIGEM_PRICED_KEY',
    'CADASTRO_OUTPUT_KEYS',
    'CADASTRO_SOURCE_SIGNATURE_KEY',
    'CADASTRO_STOCK_OUTPUT_KEYS',
    'CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY',
    'CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY',
    'CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME',
    'CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY',
    'LEGACY_CADASTRO_FINAL_KEY',
    'UNIVERSAL_FINAL_KEY',
    'activate_supplier_price_master_filter',
    'build_import_hint',
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'clear_cadastro_outputs',
    'clear_cadastro_outputs_if_source_changed',
    'enforce_cadastro_model_columns',
    'enforce_supplier_price_master_filter',
    'ensure_api_direct_final_df',
    'expected_source_rows',
    'get_cadastro_context',
    'get_context_confidence',
    'get_context_final_df',
    'get_context_mapping',
    'get_universal_final_df',
    'is_site_origin',
    'mapping_confirmed_for',
    'render_row_count_blocker',
    'render_supplier_price_master_notice',
    'row_count_matches_source',
    'set_context_final_df',
    'set_context_mapping',
    'set_mapping_confirmed',
    'set_universal_final_df',
    'store_cadastro_context',
    'store_expected_source_rows',
    'supplier_price_master_expected_rows',
    'supplier_price_master_filter_active',
    'valid_df',
    'valid_model',
]
