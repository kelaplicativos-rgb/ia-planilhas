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
CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY = 'cadastro_supplier_price_master_filter_active'
CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY = 'cadastro_supplier_price_master_rows'
CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY = 'cadastro_supplier_price_master_signature'
CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME = 'REGRA_FILTRO_MESTRE_FORNECEDOR_PRECOS'
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


def supplier_price_master_filter_active() -> bool:
    return bool(st.session_state.get(CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY, False))


def activate_supplier_price_master_filter(df_origem: pd.DataFrame | None) -> None:
    """Ativa a planilha do fornecedor como filtro mestre do resultado final.

    Regra de negócio:
    - Em atualização de preços por planilha, a planilha fornecedora é a base final.
    - Produto que não está na planilha fornecedora não deve aparecer no CSV final.
    - O modelo do Bling serve como estrutura de colunas, nunca como fonte para criar linhas extras.
    """
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
    """Impede que a base/modelo do Bling gere linhas fora da planilha fornecedora.

    Se algum módulo futuro tentar montar o CSV com mais linhas do que a origem fornecedora,
    as linhas excedentes são descartadas. Quando houver menos linhas do que a origem, o bloqueio
    continua sendo feito por render_row_count_blocker para evitar perda silenciosa.
    """
    if not supplier_price_master_filter_active() or not isinstance(df_final, pd.DataFrame):
        return df_final

    expected = supplier_price_master_expected_rows()
    if expected <= 0:
        return df_final

    if len(df_final) > expected:
        fixed = df_final.iloc[:expected].copy()
        st.session_state['df_final_cadastro'] = fixed
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

    st.warning(
        f'{CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME}: a planilha do fornecedor está sendo usada como filtro mestre. '
        'O CSV final terá somente produtos presentes na planilha fornecedora de preços.'
    )
    st.caption(
        f'Produtos na planilha fornecedora: {expected}. Produtos no resultado atual: {current}. '
        'Produtos fora da planilha fornecedora são desconsiderados.'
    )
    if removed > 0:
        st.caption(f'Blindagem aplicada: {removed} linha(s) excedente(s) foram removida(s) antes do preview/download.')


def enforce_cadastro_model_columns(df_final: pd.DataFrame | None) -> pd.DataFrame | None:
    """Mantém o cadastro fiel ao modelo anexado na primeira etapa."""
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)
    if not isinstance(df_final, pd.DataFrame) or not valid_model(df_modelo):
        return enforce_supplier_price_master_filter(df_final)
    fixed = df_final.reindex(columns=list(df_modelo.columns), fill_value='')
    fixed = enforce_supplier_price_master_filter(fixed)
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
    st.error(
        f'Proteção ativada: a planilha/origem do fornecedor tem {expected} produto(s), mas o arquivo final tem {current}. '
        'Volte para Entrada, confira a origem e refaça/confirme o mapeamento antes de baixar.'
    )
    st.caption(
        'O sistema bloqueou o avanço para evitar perda silenciosa de produtos no CSV final. '
        'Na atualização de preços por planilha, somente produtos listados pelo fornecedor podem ser gerados.'
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
    'CADASTRO_SUPPLIER_PRICE_MASTER_FILTER_KEY',
    'CADASTRO_SUPPLIER_PRICE_MASTER_ROWS_KEY',
    'CADASTRO_SUPPLIER_PRICE_MASTER_RULE_NAME',
    'CADASTRO_SUPPLIER_PRICE_MASTER_SIGNATURE_KEY',
    'activate_supplier_price_master_filter',
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'clear_cadastro_outputs',
    'clear_cadastro_outputs_if_source_changed',
    'enforce_cadastro_model_columns',
    'enforce_supplier_price_master_filter',
    'expected_source_rows',
    'is_site_origin',
    'render_row_count_blocker',
    'render_supplier_price_master_notice',
    'row_count_matches_source',
    'store_cadastro_context',
    'store_expected_source_rows',
    'supplier_price_master_expected_rows',
    'supplier_price_master_filter_active',
    'valid_df',
    'valid_model',
]
