from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.model_upload import render_model_upload_box

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
HOME_HAS_MODELS_KEY = 'home_modelos_bling_ok'
HOME_CADASTRO_MODEL_SOURCE_KEY = 'home_modelo_cadastro_source'
HOME_ESTOQUE_MODEL_SOURCE_KEY = 'home_modelo_estoque_source'
DESTINATION_MODEL_UPLOAD_OBJECT_KEY = 'destination_model_upload_object'
DESTINATION_MODEL_UPLOAD_NAME_KEY = 'destination_model_upload_name'
DESTINATION_MODEL_UPLOAD_BYTES_KEY = 'destination_model_upload_bytes'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_ORIGEM = 'origem'
MODEL_UPLOAD_SIGNATURE_KEY = 'home_model_upload_signature_v2'
MODEL_UPLOAD_AUTOFORWARDED_KEY = 'home_model_upload_autoforwarded_signature_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models.py'

GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']
DEFAULT_MODEL_SOURCE = 'padrao_sistema'


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def _df_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return 'empty'
    try:
        columns = '|'.join(map(str, df.columns))
        return f'{len(df)}x{len(df.columns)}:{columns}'
    except Exception:
        return f'{len(df)}x{len(df.columns)}'


def _df_log_summary(df: pd.DataFrame | None) -> dict[str, object]:
    if not isinstance(df, pd.DataFrame):
        return {'valid': False}
    return {
        'valid': True,
        'rows': int(len(df)),
        'columns_count': int(len(df.columns)),
        'columns': [str(column) for column in list(df.columns)[:60]],
    }


def _model_summary_df() -> pd.DataFrame | None:
    cadastro = get_home_cadastro_model()
    estoque = get_home_estoque_model()
    if isinstance(cadastro, pd.DataFrame):
        return cadastro
    if isinstance(estoque, pd.DataFrame):
        return estoque
    return None


def _models_signature(cadastro: pd.DataFrame | None, estoque: pd.DataFrame | None) -> str:
    return f'cadastro={_df_signature(cadastro)}|estoque={_df_signature(estoque)}'


def _save_model(key: str, df: pd.DataFrame | None, aliases: list[str], *, source: str = 'upload') -> None:
    copied = _copy_df(df)
    if copied is None:
        return
    st.session_state[key] = copied.copy().fillna('')
    for alias in aliases:
        st.session_state[alias] = copied.copy().fillna('')
    if key == HOME_CADASTRO_MODEL_KEY:
        st.session_state[HOME_CADASTRO_MODEL_SOURCE_KEY] = source
    elif key == HOME_ESTOQUE_MODEL_KEY:
        st.session_state[HOME_ESTOQUE_MODEL_SOURCE_KEY] = source


def _forget_model(key: str, aliases: list[str]) -> None:
    st.session_state.pop(key, None)
    for alias in aliases:
        st.session_state.pop(alias, None)
    if key == HOME_CADASTRO_MODEL_KEY:
        st.session_state.pop(HOME_CADASTRO_MODEL_SOURCE_KEY, None)
    elif key == HOME_ESTOQUE_MODEL_KEY:
        st.session_state.pop(HOME_ESTOQUE_MODEL_SOURCE_KEY, None)


def clear_default_home_models() -> None:
    if st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_CADASTRO_MODEL_KEY, GLOBAL_CADASTRO_MODEL_KEYS)
    if st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        _forget_model(HOME_ESTOQUE_MODEL_KEY, GLOBAL_ESTOQUE_MODEL_KEYS)

    for key in (
        'mapeiaai_home_intake_model_df',
        'mapeiaai_home_intake_model_file',
        'mapeiaai_final_contract_df',
        'mapeiaai_home_intake_model_type',
        'mapeiaai_home_intake_model_confidence',
    ):
        st.session_state.pop(key, None)

    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()


def _sync_detected_operation(cadastro_model_df: pd.DataFrame | None, estoque_model_df: pd.DataFrame | None) -> None:
    has_cadastro = isinstance(cadastro_model_df, pd.DataFrame) and len(cadastro_model_df.columns) > 0
    has_estoque = isinstance(estoque_model_df, pd.DataFrame) and len(estoque_model_df.columns) > 0

    if has_estoque and not has_cadastro:
        operation = 'estoque'
    elif has_cadastro and not has_estoque:
        operation = 'cadastro'
    else:
        st.session_state.pop('home_detected_operation', None)
        st.session_state.pop(FLOW_OPERATION_KEY, None)
        st.session_state.pop('operacao_final', None)
        st.session_state.pop('tipo_operacao_final', None)
        add_audit_event(
            'home_model_operation_not_detected',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='AVISO',
            details={'has_cadastro': has_cadastro, 'has_estoque': has_estoque, 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    add_audit_event(
        'home_model_operation_detected_internal_only',
        area='MODELO',
        step=st.session_state.get(WIZARD_STEP_KEY),
        status='OK',
        details={'operation': operation, 'has_cadastro': has_cadastro, 'has_estoque': has_estoque, 'visual_message': 'neutral_model_uploaded', 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operacao'] = operation
    except Exception:
        pass


def ensure_default_home_models() -> None:
    clear_default_home_models()


def save_home_models(cadastro_model_df: pd.DataFrame | None = None, estoque_model_df: pd.DataFrame | None = None, *, replace_missing: bool = True) -> None:
    clear_default_home_models()
    cadastro = _copy_df(cadastro_model_df)
    estoque = _copy_df(estoque_model_df)

    if cadastro is not None:
        _save_model(HOME_CADASTRO_MODEL_KEY, cadastro, GLOBAL_CADASTRO_MODEL_KEYS, source='upload')
    elif replace_missing:
        _forget_model(HOME_CADASTRO_MODEL_KEY, GLOBAL_CADASTRO_MODEL_KEYS)

    if estoque is not None:
        _save_model(HOME_ESTOQUE_MODEL_KEY, estoque, GLOBAL_ESTOQUE_MODEL_KEYS, source='upload')
    elif replace_missing:
        _forget_model(HOME_ESTOQUE_MODEL_KEY, GLOBAL_ESTOQUE_MODEL_KEYS)

    _sync_detected_operation(get_home_cadastro_model(), get_home_estoque_model())
    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()
    add_audit_event(
        'home_models_saved_to_session',
        area='MODELO',
        step=st.session_state.get(WIZARD_STEP_KEY),
        status='OK',
        details={
            'has_home_models': bool(st.session_state.get(HOME_HAS_MODELS_KEY)),
            'cadastro': _df_log_summary(get_home_cadastro_model()),
            'estoque': _df_log_summary(get_home_estoque_model()),
            'replace_missing': replace_missing,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def get_home_cadastro_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_CADASTRO_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_cadastro')
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def get_home_estoque_model() -> pd.DataFrame | None:
    if st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY) == DEFAULT_MODEL_SOURCE:
        return None
    df = st.session_state.get(HOME_ESTOQUE_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_estoque')
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def has_home_models() -> bool:
    return get_home_cadastro_model() is not None or get_home_estoque_model() is not None


def _render_loaded_summary() -> None:
    df = _model_summary_df()
    if not isinstance(df, pd.DataFrame):
        st.warning('Envie a planilha modelo para continuar.')
        return
    st.caption(f'Modelo enviado · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo', expanded=False):
        columns = [str(column) for column in list(df.columns)]
        st.caption(', '.join(columns))


def _auto_forward_after_first_model_upload(cadastro_model: pd.DataFrame | None, estoque_model: pd.DataFrame | None) -> None:
    signature = _models_signature(cadastro_model, estoque_model)
    if signature == 'cadastro=empty|estoque=empty':
        add_audit_event('home_model_uploaded_empty_no_autoforward', area='MODELO', step=st.session_state.get(WIZARD_STEP_KEY), status='BLOQUEADO', details={'signature': signature, 'cadastro': _df_log_summary(cadastro_model), 'estoque': _df_log_summary(estoque_model), 'responsible_file': RESPONSIBLE_FILE})
        return

    st.session_state[MODEL_UPLOAD_SIGNATURE_KEY] = signature
    previous_signature = st.session_state.get(MODEL_UPLOAD_AUTOFORWARDED_KEY)
    if previous_signature == signature:
        add_audit_event('home_model_autoforward_already_done', area='MODELO', step=st.session_state.get(WIZARD_STEP_KEY), status='OK', details={'signature': signature, 'current_step': st.session_state.get(WIZARD_STEP_KEY), 'responsible_file': RESPONSIBLE_FILE})
        return

    st.session_state[MODEL_UPLOAD_AUTOFORWARDED_KEY] = signature
    st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
    add_audit_event('home_model_uploaded_auto_forward_to_origin', area='MODELO', step=STEP_ORIGEM, status='OK', details={'signature': signature, 'previous_signature': previous_signature, 'target_step': STEP_ORIGEM, 'cadastro': _df_log_summary(cadastro_model), 'estoque': _df_log_summary(estoque_model), 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['step'] = STEP_ORIGEM
    except Exception as exc:
        add_audit_event('home_model_autoforward_query_param_failed', area='MODELO', step=STEP_ORIGEM, status='AVISO', details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _remember_original_model_upload(upload: object) -> None:
    model_file = getattr(upload, 'model_file', None) or getattr(upload, 'cadastro_model_file', None) or getattr(upload, 'estoque_model_file', None)
    if model_file is None:
        return

    file_name = str(getattr(model_file, 'name', 'modelo'))
    file_bytes = b''
    try:
        raw = model_file.getvalue()
        file_bytes = bytes(raw) if raw is not None else b''
    except Exception:
        file_bytes = b''

    st.session_state[DESTINATION_MODEL_UPLOAD_OBJECT_KEY] = model_file
    st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = file_name
    if file_bytes:
        st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = file_bytes

    add_audit_event(
        'destination_model_upload_object_saved',
        area='MODELO',
        status='OK',
        details={
            'name': file_name,
            'bytes_saved': bool(file_bytes),
            'bytes_len': len(file_bytes),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def render_home_bling_models() -> None:
    clear_default_home_models()
    st.markdown('#### Planilha modelo para o mapeamento')
    st.caption('Envie a planilha modelo que o sistema vai preencher no final.')

    upload = render_model_upload_box(title='Enviar planilha modelo', operation='cadastro', key='home_model_upload_bling', required_model=False, caption=None)
    cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else None
    estoque_model = upload.estoque_model_df if isinstance(upload.estoque_model_df, pd.DataFrame) else None

    if isinstance(cadastro_model, pd.DataFrame) or isinstance(estoque_model, pd.DataFrame):
        _remember_original_model_upload(upload)
        add_audit_event('home_model_upload_ready_to_save', area='MODELO', step=st.session_state.get(WIZARD_STEP_KEY), status='OK', details={'cadastro': _df_log_summary(cadastro_model), 'estoque': _df_log_summary(estoque_model), 'responsible_file': RESPONSIBLE_FILE})
        save_home_models(cadastro_model, estoque_model, replace_missing=True)
        _auto_forward_after_first_model_upload(cadastro_model, estoque_model)

    _render_loaded_summary()


__all__ = [
    'DESTINATION_MODEL_UPLOAD_BYTES_KEY',
    'DESTINATION_MODEL_UPLOAD_NAME_KEY',
    'DESTINATION_MODEL_UPLOAD_OBJECT_KEY',
    'clear_default_home_models',
    'ensure_default_home_models',
    'get_home_cadastro_model',
    'get_home_estoque_model',
    'has_home_models',
    'render_home_bling_models',
    'save_home_models',
]