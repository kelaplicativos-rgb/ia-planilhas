from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.universal.model_contract_detector import (
    CONTRACT_LABELS,
    MODEL_CONTRACT_CONFIDENCE_KEY,
    MODEL_CONTRACT_LABEL_KEY,
    MODEL_CONTRACT_REASON_KEY,
    MODEL_CONTRACT_TYPE_KEY,
    detect_model_contract,
    normalize_contract_operation,
)

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
HOME_PRECO_MODEL_KEY = 'home_modelo_atualizacao_preco_df'
HOME_UNIVERSAL_MODEL_KEY = 'home_modelo_universal_df'
HOME_HAS_MODELS_KEY = 'home_modelos_bling_ok'
HOME_CADASTRO_MODEL_SOURCE_KEY = 'home_modelo_cadastro_source'
HOME_ESTOQUE_MODEL_SOURCE_KEY = 'home_modelo_estoque_source'
HOME_PRECO_MODEL_SOURCE_KEY = 'home_modelo_atualizacao_preco_source'
HOME_UNIVERSAL_MODEL_SOURCE_KEY = 'home_modelo_universal_source'
DESTINATION_MODEL_UPLOAD_OBJECT_KEY = 'destination_model_upload_object'
DESTINATION_MODEL_UPLOAD_NAME_KEY = 'destination_model_upload_name'
DESTINATION_MODEL_UPLOAD_BYTES_KEY = 'destination_model_upload_bytes'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_ORIGEM = 'origem'
UNIVERSAL_OPERATION = 'universal'
MODEL_UPLOAD_SIGNATURE_KEY = 'home_model_upload_signature_v2'
MODEL_UPLOAD_AUTOFORWARDED_KEY = 'home_model_upload_autoforwarded_signature_v2'
MODEL_SAVE_SIGNATURE_KEY = 'home_model_save_signature_v3'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models_state.py'

GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']
GLOBAL_PRECO_MODEL_KEYS = ['df_modelo_atualizacao_preco', 'modelo_atualizacao_preco_df']
GLOBAL_UNIVERSAL_MODEL_KEYS = ['df_modelo_universal', 'modelo_universal_df']
DEFAULT_MODEL_SOURCE = 'padrao_sistema'


def copy_home_model_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def df_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return 'empty'
    try:
        columns = '|'.join(map(str, df.columns))
        return f'{len(df)}x{len(df.columns)}:{columns}'
    except Exception:
        return f'{len(df)}x{len(df.columns)}'


def df_log_summary(df: pd.DataFrame | None) -> dict[str, object]:
    if not isinstance(df, pd.DataFrame):
        return {'valid': False}
    return {
        'valid': True,
        'rows': int(len(df)),
        'columns_count': int(len(df.columns)),
        'columns': [str(column) for column in list(df.columns)[:60]],
    }


def models_signature(cadastro: pd.DataFrame | None, estoque: pd.DataFrame | None, preco: pd.DataFrame | None = None, universal: pd.DataFrame | None = None) -> str:
    return f'cadastro={df_signature(cadastro)}|estoque={df_signature(estoque)}|preco={df_signature(preco)}|universal={df_signature(universal)}'


def _save_model(key: str, df: pd.DataFrame | None, aliases: list[str], *, source: str = 'upload') -> None:
    copied = copy_home_model_df(df)
    if copied is None:
        return
    st.session_state[key] = copied.copy().fillna('')
    for alias in aliases:
        st.session_state[alias] = copied.copy().fillna('')
    if key == HOME_CADASTRO_MODEL_KEY:
        st.session_state[HOME_CADASTRO_MODEL_SOURCE_KEY] = source
    elif key == HOME_ESTOQUE_MODEL_KEY:
        st.session_state[HOME_ESTOQUE_MODEL_SOURCE_KEY] = source
    elif key == HOME_PRECO_MODEL_KEY:
        st.session_state[HOME_PRECO_MODEL_SOURCE_KEY] = source
    elif key == HOME_UNIVERSAL_MODEL_KEY:
        st.session_state[HOME_UNIVERSAL_MODEL_SOURCE_KEY] = source


def _forget_model(key: str, aliases: list[str]) -> None:
    st.session_state.pop(key, None)
    for alias in aliases:
        st.session_state.pop(alias, None)
    if key == HOME_CADASTRO_MODEL_KEY:
        st.session_state.pop(HOME_CADASTRO_MODEL_SOURCE_KEY, None)
    elif key == HOME_ESTOQUE_MODEL_KEY:
        st.session_state.pop(HOME_ESTOQUE_MODEL_SOURCE_KEY, None)
    elif key == HOME_PRECO_MODEL_KEY:
        st.session_state.pop(HOME_PRECO_MODEL_SOURCE_KEY, None)
    elif key == HOME_UNIVERSAL_MODEL_KEY:
        st.session_state.pop(HOME_UNIVERSAL_MODEL_SOURCE_KEY, None)


def clear_default_home_models() -> None:
    if st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_CADASTRO_MODEL_KEY, GLOBAL_CADASTRO_MODEL_KEYS)
    if st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_ESTOQUE_MODEL_KEY, GLOBAL_ESTOQUE_MODEL_KEYS)
    if st.session_state.get(HOME_PRECO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_PRECO_MODEL_KEY, GLOBAL_PRECO_MODEL_KEYS)
    if st.session_state.get(HOME_UNIVERSAL_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_UNIVERSAL_MODEL_KEY, GLOBAL_UNIVERSAL_MODEL_KEYS)

    for key in (
        'mapeiaai_home_intake_model_df',
        'mapeiaai_home_intake_model_file',
        'mapeiaai_final_contract_df',
        'mapeiaai_home_intake_model_type',
        'mapeiaai_home_intake_model_confidence',
    ):
        st.session_state.pop(key, None)

    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()


def _current_detected_contract(cadastro_model_df: pd.DataFrame | None, estoque_model_df: pd.DataFrame | None, preco_model_df: pd.DataFrame | None = None, universal_model_df: pd.DataFrame | None = None) -> str:
    explicit = normalize_contract_operation(st.session_state.get(MODEL_CONTRACT_TYPE_KEY))
    if explicit:
        return explicit
    for df in (estoque_model_df, preco_model_df, cadastro_model_df, universal_model_df):
        copied = copy_home_model_df(df)
        if copied is not None:
            return detect_model_contract(copied).contract_type
    return ''


def sync_universal_operation(
    cadastro_model_df: pd.DataFrame | None,
    estoque_model_df: pd.DataFrame | None,
    preco_model_df: pd.DataFrame | None = None,
    universal_model_df: pd.DataFrame | None = None,
) -> None:
    """Sincroniza a operação com o contrato real detectado, sem forçar universal."""
    has_cadastro = isinstance(cadastro_model_df, pd.DataFrame) and len(cadastro_model_df.columns) > 0
    has_estoque = isinstance(estoque_model_df, pd.DataFrame) and len(estoque_model_df.columns) > 0
    has_preco = isinstance(preco_model_df, pd.DataFrame) and len(preco_model_df.columns) > 0
    has_universal = isinstance(universal_model_df, pd.DataFrame) and len(universal_model_df.columns) > 0

    if not any([has_cadastro, has_estoque, has_preco, has_universal]):
        st.session_state.pop('home_detected_operation', None)
        st.session_state.pop(FLOW_OPERATION_KEY, None)
        st.session_state.pop('operacao_final', None)
        st.session_state.pop('tipo_operacao_final', None)
        add_audit_event('home_model_operation_not_detected', area='MODELO', step=st.session_state.get(WIZARD_STEP_KEY), status='AVISO', details={'has_cadastro': has_cadastro, 'has_estoque': has_estoque, 'has_preco': has_preco, 'has_universal': has_universal, 'responsible_file': RESPONSIBLE_FILE})
        return

    operation = _current_detected_contract(cadastro_model_df, estoque_model_df, preco_model_df, universal_model_df) or UNIVERSAL_OPERATION
    label = CONTRACT_LABELS.get(operation, CONTRACT_LABELS['universal'])
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = operation
    st.session_state[MODEL_CONTRACT_LABEL_KEY] = label
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    try:
        st.query_params['operacao'] = operation
    except Exception:
        pass
    add_audit_event(
        'home_model_operation_real_contract_synced',
        area='MODELO',
        step=st.session_state.get(WIZARD_STEP_KEY),
        status='OK',
        details={
            'operation': operation,
            'label': label,
            'has_cadastro': has_cadastro,
            'has_estoque': has_estoque,
            'has_preco': has_preco,
            'has_universal': has_universal,
            'confidence': st.session_state.get(MODEL_CONTRACT_CONFIDENCE_KEY),
            'reason': st.session_state.get(MODEL_CONTRACT_REASON_KEY),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def ensure_default_home_models() -> None:
    clear_default_home_models()


def save_home_models(cadastro_model_df: pd.DataFrame | None = None, estoque_model_df: pd.DataFrame | None = None, preco_model_df: pd.DataFrame | None = None, universal_model_df: pd.DataFrame | None = None, *, replace_missing: bool = True) -> None:
    clear_default_home_models()
    cadastro = copy_home_model_df(cadastro_model_df)
    estoque = copy_home_model_df(estoque_model_df)
    preco = copy_home_model_df(preco_model_df)
    universal = copy_home_model_df(universal_model_df)

    if universal is None and cadastro is not None and normalize_contract_operation(st.session_state.get(MODEL_CONTRACT_TYPE_KEY)) == 'universal':
        universal = cadastro.copy().fillna('')
        cadastro = None

    signature = models_signature(cadastro, estoque, preco, universal)
    previous_signature = str(st.session_state.get(MODEL_SAVE_SIGNATURE_KEY) or '')

    if previous_signature != signature:
        if cadastro is not None:
            _save_model(HOME_CADASTRO_MODEL_KEY, cadastro, GLOBAL_CADASTRO_MODEL_KEYS, source='upload')
        elif replace_missing:
            _forget_model(HOME_CADASTRO_MODEL_KEY, GLOBAL_CADASTRO_MODEL_KEYS)

        if estoque is not None:
            _save_model(HOME_ESTOQUE_MODEL_KEY, estoque, GLOBAL_ESTOQUE_MODEL_KEYS, source='upload')
        elif replace_missing:
            _forget_model(HOME_ESTOQUE_MODEL_KEY, GLOBAL_ESTOQUE_MODEL_KEYS)

        if preco is not None:
            _save_model(HOME_PRECO_MODEL_KEY, preco, GLOBAL_PRECO_MODEL_KEYS, source='upload')
        elif replace_missing:
            _forget_model(HOME_PRECO_MODEL_KEY, GLOBAL_PRECO_MODEL_KEYS)

        if universal is not None:
            _save_model(HOME_UNIVERSAL_MODEL_KEY, universal, GLOBAL_UNIVERSAL_MODEL_KEYS, source='upload')
        elif replace_missing:
            _forget_model(HOME_UNIVERSAL_MODEL_KEY, GLOBAL_UNIVERSAL_MODEL_KEYS)

        st.session_state[MODEL_SAVE_SIGNATURE_KEY] = signature

    sync_universal_operation(get_home_cadastro_model(), get_home_estoque_model(), get_home_preco_model(), get_home_universal_model())
    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()
    add_audit_event(
        'home_models_saved_to_session',
        area='MODELO',
        step=st.session_state.get(WIZARD_STEP_KEY),
        status='OK',
        details={
            'has_home_models': bool(st.session_state.get(HOME_HAS_MODELS_KEY)),
            'contract_type': st.session_state.get(MODEL_CONTRACT_TYPE_KEY),
            'contract_label': st.session_state.get(MODEL_CONTRACT_LABEL_KEY),
            'cadastro': df_log_summary(get_home_cadastro_model()),
            'estoque': df_log_summary(get_home_estoque_model()),
            'preco': df_log_summary(get_home_preco_model()),
            'universal': df_log_summary(get_home_universal_model()),
            'replace_missing': replace_missing,
            'signature_changed': previous_signature != signature,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def get_home_cadastro_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_CADASTRO_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_cadastro')
    return copy_home_model_df(df) if isinstance(df, pd.DataFrame) else None


def get_home_estoque_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_ESTOQUE_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_estoque')
    return copy_home_model_df(df) if isinstance(df, pd.DataFrame) else None


def get_home_preco_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_PRECO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_PRECO_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_atualizacao_preco')
    return copy_home_model_df(df) if isinstance(df, pd.DataFrame) else None


def get_home_universal_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_UNIVERSAL_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_UNIVERSAL_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_universal')
    return copy_home_model_df(df) if isinstance(df, pd.DataFrame) else None


def has_home_models() -> bool:
    return any(model is not None for model in (get_home_cadastro_model(), get_home_estoque_model(), get_home_preco_model(), get_home_universal_model()))


__all__ = [
    'DEFAULT_MODEL_SOURCE',
    'DESTINATION_MODEL_UPLOAD_BYTES_KEY',
    'DESTINATION_MODEL_UPLOAD_NAME_KEY',
    'DESTINATION_MODEL_UPLOAD_OBJECT_KEY',
    'FLOW_OPERATION_KEY',
    'HOME_CADASTRO_MODEL_KEY',
    'HOME_CADASTRO_MODEL_SOURCE_KEY',
    'HOME_ESTOQUE_MODEL_KEY',
    'HOME_ESTOQUE_MODEL_SOURCE_KEY',
    'HOME_PRECO_MODEL_KEY',
    'HOME_PRECO_MODEL_SOURCE_KEY',
    'HOME_UNIVERSAL_MODEL_KEY',
    'HOME_UNIVERSAL_MODEL_SOURCE_KEY',
    'HOME_HAS_MODELS_KEY',
    'MODEL_UPLOAD_AUTOFORWARDED_KEY',
    'MODEL_UPLOAD_SIGNATURE_KEY',
    'STEP_ORIGEM',
    'UNIVERSAL_OPERATION',
    'WIZARD_STEP_KEY',
    'clear_default_home_models',
    'copy_home_model_df',
    'df_log_summary',
    'df_signature',
    'ensure_default_home_models',
    'get_home_cadastro_model',
    'get_home_estoque_model',
    'get_home_preco_model',
    'get_home_universal_model',
    'has_home_models',
    'models_signature',
    'save_home_models',
]
