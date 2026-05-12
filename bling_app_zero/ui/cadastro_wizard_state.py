from __future__ import annotations

import pandas as pd
import streamlit as st

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
BLING_IMPORTADOR_PRODUTOS_URL = 'https://www.bling.com.br/importador.produtos.php'

CADASTRO_OUTPUT_KEYS = [
    'df_final_cadastro',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
    'df_origem_cadastro_precificada',
    'df_final_estoque_from_cadastro',
    'mapping_estoque_from_cadastro',
    'mapping_confidence_estoque_from_cadastro',
    CADASTRO_ORIGEM_PRICED_KEY,
    CADASTRO_MAPPING_CONFIRMED_KEY,
    CADASTRO_MAPPING_SIGNATURE_KEY,
]


def valid_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def valid_model(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def is_site_origin() -> bool:
    return str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '').strip().lower() == 'site'


def enforce_cadastro_model_columns(df_final: pd.DataFrame | None) -> pd.DataFrame | None:
    """Mantém o cadastro fiel ao modelo anexado na primeira etapa."""
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    if not isinstance(df_final, pd.DataFrame) or not valid_model(df_modelo):
        return df_final
    fixed = df_final.reindex(columns=list(df_modelo.columns), fill_value='')
    st.session_state['df_final_cadastro'] = fixed
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
    expected = expected_source_rows()
    if expected <= 0:
        return True
    return isinstance(df_final, pd.DataFrame) and len(df_final) == expected


def render_row_count_blocker(df_final: pd.DataFrame | None) -> bool:
    expected = expected_source_rows()
    current = len(df_final) if isinstance(df_final, pd.DataFrame) else 0
    if expected <= 0 or current == expected:
        return False
    st.error(
        f'Proteção ativada: a origem tem {expected} produto(s), mas o arquivo final tem {current}. '
        'Volte para Entrada, confira a origem por site e refaça/confirmar o mapeamento antes de baixar.'
    )
    st.caption('O sistema bloqueou o avanço para evitar perda silenciosa de produtos no CSV final.')
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
    else:
        st.session_state.pop(CADASTRO_ORIGEM_KEY, None)
        store_expected_source_rows(None)

    if valid_model(df_modelo):
        st.session_state[CADASTRO_MODELO_KEY] = df_modelo
    else:
        st.session_state.pop(CADASTRO_MODELO_KEY, None)

    if valid_model(df_modelo_estoque):
        st.session_state[CADASTRO_MODELO_ESTOQUE_KEY] = df_modelo_estoque
    else:
        st.session_state.pop(CADASTRO_MODELO_ESTOQUE_KEY, None)


def cadastro_context_ready() -> bool:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    return valid_df(df_origem) and valid_model(df_modelo)


def cadastro_mapping_ready() -> bool:
    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    mapping = st.session_state.get('mapping_cadastro')
    confirmed = bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY))
    return valid_df(df_final) and row_count_matches_source(df_final) and isinstance(mapping, dict) and bool(mapping) and confirmed


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
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'clear_cadastro_outputs',
    'clear_cadastro_outputs_if_source_changed',
    'enforce_cadastro_model_columns',
    'expected_source_rows',
    'is_site_origin',
    'render_row_count_blocker',
    'row_count_matches_source',
    'store_cadastro_context',
    'store_expected_source_rows',
    'valid_df',
    'valid_model',
]
