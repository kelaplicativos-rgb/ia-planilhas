from __future__ import annotations

import pandas as pd
import streamlit as st

SITE_SOURCE_KEY = 'df_origem_site_como_planilha'
SITE_OPERATION_KEY = 'site_operation_como_planilha'
SITE_SOURCE_URLS_KEY = 'site_source_urls_como_planilha'
SITE_REQUESTED_COLUMNS_KEY = 'site_requested_columns_como_planilha'
SITE_CADASTRO_MODEL_KEY = 'site_modelo_cadastro_como_planilha'
SITE_ESTOQUE_MODEL_KEY = 'site_modelo_estoque_como_planilha'
SITE_OPERATION_MODEL_KEY = 'site_modelo_operacao_como_planilha'
SITE_RAW_LEGACY_KEY = 'df_site_bruto'
SITE_RAW_OPERATION_KEY = 'operation_site'
SITE_RAW_OPERATION_TYPE_KEY = 'tipo_operacao_site'

CADASTRO_WIZARD_ORIGEM_KEY = 'cadastro_wizard_df_origem'
CADASTRO_WIZARD_PARA_MAPEAR_KEY = 'cadastro_wizard_df_para_mapear'
CADASTRO_WIZARD_MODELO_KEY = 'cadastro_wizard_df_modelo'
CADASTRO_WIZARD_MODELO_ESTOQUE_KEY = 'cadastro_wizard_df_modelo_estoque'
CADASTRO_EXPECTED_ROWS_KEY = 'cadastro_wizard_expected_source_rows'
CADASTRO_EXPECTED_SIGNATURE_KEY = 'cadastro_wizard_expected_source_signature'
ESTOQUE_WIZARD_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_WIZARD_MODELO_KEY = 'estoque_wizard_df_modelo'

PLANILHA_SOURCE_KEYS = [
    'df_origem',
    'df_origem_cadastro',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_source',
]
ESTOQUE_SOURCE_KEYS = [
    'df_origem_estoque',
    'df_estoque_origem',
    'df_source_estoque',
]
PLANILHA_MODEL_CADASTRO_KEYS = [
    'df_modelo_cadastro',
    'modelo_cadastro_df',
]
PLANILHA_MODEL_ESTOQUE_KEYS = [
    'df_modelo_estoque',
    'modelo_estoque_df',
]


def _op_key(operation: str) -> str:
    return _normalize_operation(operation)


def _source_key(operation: str) -> str:
    return f'{SITE_SOURCE_KEY}_{_op_key(operation)}'


def _raw_source_key(operation: str) -> str:
    return f'{SITE_RAW_LEGACY_KEY}_{_op_key(operation)}'


def _urls_key(operation: str) -> str:
    return f'{SITE_SOURCE_URLS_KEY}_{_op_key(operation)}'


def _columns_key(operation: str) -> str:
    return f'{SITE_REQUESTED_COLUMNS_KEY}_{_op_key(operation)}'


def _normalize_operation(operation: str | None) -> str:
    text = str(operation or '').strip().lower()
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    return 'cadastro'


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def _df_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'empty'
    try:
        columns = '|'.join(map(str, df.columns))
        shape = f'{len(df)}x{len(df.columns)}'
        sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
        return f'{shape}:{columns}:{sample}'
    except Exception:
        return f'{len(df)}x{len(df.columns)}'


def _clear_output_cache_for_operation(operation: str) -> None:
    normalized = _normalize_operation(operation)
    keys = []
    if normalized == 'cadastro':
        keys.extend([
            'df_final_cadastro',
            'mapping_cadastro',
            'mapping_confidence_cadastro',
            'df_origem_cadastro_precificada',
            'cadastro_preco_calculado_ativo',
            'df_final_estoque_from_cadastro',
            'mapping_estoque_from_cadastro',
            'mapping_confidence_estoque_from_cadastro',
            CADASTRO_WIZARD_PARA_MAPEAR_KEY,
            'cadastro_mapping_confirmed',
            'cadastro_mapping_confirmed_signature',
        ])
    else:
        keys.extend([
            'estoque_multi_outputs',
            'df_final_estoque',
            'mapping_estoque',
        ])
    for key in keys:
        st.session_state.pop(key, None)


def _mirror_as_uploaded_planilha(
    df: pd.DataFrame,
    operation: str,
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
) -> None:
    normalized = _normalize_operation(operation)
    copied_origin = _copy_df(df)
    origem = copied_origin if copied_origin is not None else pd.DataFrame()

    if normalized == 'cadastro':
        for key in PLANILHA_SOURCE_KEYS:
            st.session_state[key] = origem.copy().fillna('')
        for key in ESTOQUE_SOURCE_KEYS:
            st.session_state.pop(key, None)
    else:
        for key in ESTOQUE_SOURCE_KEYS:
            st.session_state[key] = origem.copy().fillna('')
        for key in PLANILHA_SOURCE_KEYS:
            st.session_state.pop(key, None)

    cadastro_model = _copy_df(cadastro_model_df)
    estoque_model = _copy_df(estoque_model_df)

    if cadastro_model is not None:
        for key in PLANILHA_MODEL_CADASTRO_KEYS:
            st.session_state[key] = cadastro_model.copy().fillna('')
    if estoque_model is not None:
        for key in PLANILHA_MODEL_ESTOQUE_KEYS:
            st.session_state[key] = estoque_model.copy().fillna('')

    st.session_state['origem_dados'] = 'planilha'
    st.session_state['origem_tipo'] = 'planilha'
    st.session_state['origem_planilha_via_site'] = True
    st.session_state['site_gerou_origem_planilha'] = True
    st.session_state['tipo_operacao'] = normalized
    st.session_state['operacao_final'] = normalized
    st.session_state['tipo_operacao_final'] = normalized


def _mirror_to_wizard_keys(
    *,
    source_df: pd.DataFrame,
    operation: str,
    cadastro_model_df: pd.DataFrame | None,
    estoque_model_df: pd.DataFrame | None,
    operation_model_df: pd.DataFrame | None,
) -> None:
    """Ponte BLINGFIX: captura por site precisa alimentar as chaves do Wizard atual."""
    normalized = _normalize_operation(operation)
    origem = source_df.copy().fillna('') if isinstance(source_df, pd.DataFrame) else pd.DataFrame()
    cadastro_model = _copy_df(cadastro_model_df)
    estoque_model = _copy_df(estoque_model_df)
    operation_model = _copy_df(operation_model_df)

    if normalized == 'cadastro':
        if cadastro_model is None:
            cadastro_model = operation_model
        st.session_state[CADASTRO_WIZARD_ORIGEM_KEY] = origem.copy().fillna('')
        # Esta chave é recriada depois pela precificação/mapeamento quando houver preço calculado.
        # Aqui ela também serve como origem pronta para diagnóstico e para não deixar o Wizard sem contexto.
        st.session_state[CADASTRO_WIZARD_PARA_MAPEAR_KEY] = origem.copy().fillna('')
        st.session_state[CADASTRO_EXPECTED_ROWS_KEY] = int(len(origem))
        st.session_state[CADASTRO_EXPECTED_SIGNATURE_KEY] = _df_signature(origem)
        if cadastro_model is not None:
            st.session_state[CADASTRO_WIZARD_MODELO_KEY] = cadastro_model.copy().fillna('')
        if estoque_model is not None:
            st.session_state[CADASTRO_WIZARD_MODELO_ESTOQUE_KEY] = estoque_model.copy().fillna('')
        st.session_state.pop(ESTOQUE_WIZARD_ORIGEM_SITE_KEY, None)
    else:
        if estoque_model is None:
            estoque_model = operation_model
        st.session_state[ESTOQUE_WIZARD_ORIGEM_SITE_KEY] = origem.copy().fillna('')
        if estoque_model is not None:
            st.session_state[ESTOQUE_WIZARD_MODELO_KEY] = estoque_model.copy().fillna('')

    st.session_state['site_capture_result_ready'] = bool(not origem.empty)
    st.session_state['site_capture_finished'] = True
    st.session_state['site_capture_error'] = ''
    st.session_state['site_capture_operation'] = normalized
    st.session_state['site_capture_rows'] = int(len(origem))
    st.session_state['site_capture_columns'] = int(len(origem.columns))


def set_site_source_as_planilha(
    df: pd.DataFrame,
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None = None,
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
    operation_model_df: pd.DataFrame | None = None,
) -> None:
    """Registra a captura por site como origem equivalente a uma planilha carregada."""
    normalized = _normalize_operation(operation)
    source_df = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()

    st.session_state[SITE_SOURCE_KEY] = source_df
    st.session_state[_source_key(normalized)] = source_df.copy().fillna('')
    st.session_state[_raw_source_key(normalized)] = source_df.copy().fillna('')
    st.session_state[SITE_RAW_LEGACY_KEY] = source_df.copy().fillna('')
    st.session_state[SITE_OPERATION_KEY] = normalized
    st.session_state[SITE_RAW_OPERATION_KEY] = normalized
    st.session_state[SITE_RAW_OPERATION_TYPE_KEY] = normalized
    st.session_state[SITE_SOURCE_URLS_KEY] = raw_urls
    st.session_state[_urls_key(normalized)] = raw_urls
    st.session_state[SITE_REQUESTED_COLUMNS_KEY] = list(requested_columns or [])
    st.session_state[_columns_key(normalized)] = list(requested_columns or [])

    other = 'estoque' if normalized == 'cadastro' else 'cadastro'
    st.session_state.pop(_raw_source_key(other), None)

    cadastro_model = _copy_df(cadastro_model_df)
    estoque_model = _copy_df(estoque_model_df)
    operation_model = _copy_df(operation_model_df)

    if normalized == 'estoque' and estoque_model is None:
        estoque_model = operation_model
    if normalized == 'cadastro' and cadastro_model is None:
        cadastro_model = operation_model

    if cadastro_model is not None:
        st.session_state[SITE_CADASTRO_MODEL_KEY] = cadastro_model
    if estoque_model is not None:
        st.session_state[SITE_ESTOQUE_MODEL_KEY] = estoque_model
    if operation_model is not None:
        st.session_state[SITE_OPERATION_MODEL_KEY] = operation_model

    _clear_output_cache_for_operation(normalized)
    _mirror_as_uploaded_planilha(
        df=source_df,
        operation=normalized,
        cadastro_model_df=cadastro_model,
        estoque_model_df=estoque_model,
    )
    _mirror_to_wizard_keys(
        source_df=source_df,
        operation=normalized,
        cadastro_model_df=cadastro_model,
        estoque_model_df=estoque_model,
        operation_model_df=operation_model,
    )


def get_site_source_for_operation(operation: str) -> pd.DataFrame | None:
    normalized = _normalize_operation(operation)
    df = st.session_state.get(_source_key(normalized))
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')

    saved_operation = st.session_state.get(SITE_OPERATION_KEY)
    df = st.session_state.get(SITE_SOURCE_KEY)
    if saved_operation != normalized:
        return None
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')
    return None


def get_site_model_for_operation(operation: str) -> pd.DataFrame | None:
    normalized = _normalize_operation(operation)
    if normalized == 'cadastro':
        df = st.session_state.get(SITE_CADASTRO_MODEL_KEY)
        if not isinstance(df, pd.DataFrame):
            df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    elif normalized == 'estoque':
        df = st.session_state.get(SITE_ESTOQUE_MODEL_KEY)
        if not isinstance(df, pd.DataFrame):
            df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    else:
        df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def get_site_estoque_model() -> pd.DataFrame | None:
    df = st.session_state.get(SITE_ESTOQUE_MODEL_KEY)
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def clear_site_source(operation: str | None = None) -> None:
    operations = [_normalize_operation(operation)] if operation else ['cadastro', 'estoque']
    for op in operations:
        for key in [_source_key(op), _raw_source_key(op), _urls_key(op), _columns_key(op)]:
            st.session_state.pop(key, None)
        _clear_output_cache_for_operation(op)

    if operation is None:
        for key in [
            SITE_SOURCE_KEY,
            SITE_OPERATION_KEY,
            SITE_SOURCE_URLS_KEY,
            SITE_REQUESTED_COLUMNS_KEY,
            SITE_CADASTRO_MODEL_KEY,
            SITE_ESTOQUE_MODEL_KEY,
            SITE_OPERATION_MODEL_KEY,
            SITE_RAW_LEGACY_KEY,
            SITE_RAW_OPERATION_KEY,
            SITE_RAW_OPERATION_TYPE_KEY,
            *PLANILHA_SOURCE_KEYS,
            *ESTOQUE_SOURCE_KEYS,
            *PLANILHA_MODEL_CADASTRO_KEYS,
            *PLANILHA_MODEL_ESTOQUE_KEYS,
            CADASTRO_WIZARD_ORIGEM_KEY,
            CADASTRO_WIZARD_PARA_MAPEAR_KEY,
            CADASTRO_WIZARD_MODELO_KEY,
            CADASTRO_WIZARD_MODELO_ESTOQUE_KEY,
            CADASTRO_EXPECTED_ROWS_KEY,
            CADASTRO_EXPECTED_SIGNATURE_KEY,
            ESTOQUE_WIZARD_ORIGEM_SITE_KEY,
            ESTOQUE_WIZARD_MODELO_KEY,
            'origem_dados',
            'origem_tipo',
            'origem_planilha_via_site',
            'site_gerou_origem_planilha',
            'tipo_operacao',
            'operacao_final',
            'tipo_operacao_final',
            'site_capture_running',
            'site_capture_finished',
            'site_capture_result_ready',
            'site_capture_error',
            'site_capture_rows',
            'site_capture_columns',
        ]:
            st.session_state.pop(key, None)


def has_site_source(operation: str) -> bool:
    return get_site_source_for_operation(operation) is not None
