from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.engines.cadastro_engine import default_model as default_cadastro_model
from bling_app_zero.flows.estoque_contract import default_model as default_estoque_model
from bling_app_zero.ui.model_upload import render_model_upload_box
from bling_app_zero.universal.model_detector import detect_model_type

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
HOME_HAS_MODELS_KEY = 'home_modelos_bling_ok'
HOME_CADASTRO_MODEL_SOURCE_KEY = 'home_modelo_cadastro_source'
HOME_ESTOQUE_MODEL_SOURCE_KEY = 'home_modelo_estoque_source'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'

GLOBAL_CADASTRO_MODEL_KEYS = [
    'df_modelo_cadastro',
    'modelo_cadastro_df',
]
GLOBAL_ESTOQUE_MODEL_KEYS = [
    'df_modelo_estoque',
    'modelo_estoque_df',
]


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


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


def _sync_detected_operation(cadastro_model_df: pd.DataFrame | None, estoque_model_df: pd.DataFrame | None) -> None:
    has_cadastro = isinstance(cadastro_model_df, pd.DataFrame) and len(cadastro_model_df.columns) > 0
    has_estoque = isinstance(estoque_model_df, pd.DataFrame) and len(estoque_model_df.columns) > 0

    if has_estoque and not has_cadastro:
        operation = 'estoque'
    elif has_cadastro and not has_estoque:
        operation = 'cadastro'
    else:
        st.session_state.pop('home_detected_operation', None)
        return

    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    try:
        st.query_params['operacao'] = operation
    except Exception:
        pass


def ensure_default_home_models() -> None:
    """Garante modelos padrão internos quando o usuário não anexar modelo.

    Isso evita exigir upload em todo uso. Se o usuário anexar um modelo de destino,
    o upload substitui somente aquele tipo e o outro modelo já salvo é preservado.
    """
    if get_home_cadastro_model() is None:
        _save_model(HOME_CADASTRO_MODEL_KEY, default_cadastro_model(), GLOBAL_CADASTRO_MODEL_KEYS, source='padrao_sistema')
    if get_home_estoque_model() is None:
        _save_model(HOME_ESTOQUE_MODEL_KEY, default_estoque_model(), GLOBAL_ESTOQUE_MODEL_KEYS, source='padrao_sistema')
    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()


def save_home_models(
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
    *,
    replace_missing: bool = False,
) -> None:
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

    ensure_default_home_models()
    _sync_detected_operation(get_home_cadastro_model(), get_home_estoque_model())
    st.session_state[HOME_HAS_MODELS_KEY] = has_home_models()


def get_home_cadastro_model() -> pd.DataFrame | None:
    df = st.session_state.get(HOME_CADASTRO_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_cadastro')
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def get_home_estoque_model() -> pd.DataFrame | None:
    df = st.session_state.get(HOME_ESTOQUE_MODEL_KEY)
    if not isinstance(df, pd.DataFrame):
        df = st.session_state.get('df_modelo_estoque')
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def has_home_models() -> bool:
    return get_home_cadastro_model() is not None or get_home_estoque_model() is not None


def _model_source_label(source: object) -> str:
    text = str(source or '').strip()
    if text == 'upload':
        return 'modelo anexado'
    if text == 'padrao_sistema':
        return 'padrão salvo do sistema'
    return 'modelo disponível'


def _render_detection_badge(label: str, df: pd.DataFrame, source: object) -> None:
    detection = detect_model_type(df)
    st.caption(
        f'{label}: {len(df.columns)} coluna(s) · tipo detectado: {detection.model_type} '
        f'({round(detection.confidence * 100)}%) · {_model_source_label(source)}'
    )
    if detection.model_type == 'personalizado':
        st.info('Modelo personalizado: a planilha final ainda respeitará exatamente as colunas e a ordem do arquivo anexado.')
    else:
        st.success(f'Modelo interpretado como {detection.model_type}. {detection.reason}')


def _render_loaded_summary() -> None:
    cadastro = get_home_cadastro_model()
    estoque = get_home_estoque_model()
    parts: list[str] = []
    if isinstance(cadastro, pd.DataFrame):
        parts.append(f'cadastro ({_model_source_label(st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY))})')
    if isinstance(estoque, pd.DataFrame):
        parts.append(f'estoque ({_model_source_label(st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY))})')
    if parts:
        st.success('Modelos disponíveis: ' + ' + '.join(parts))

    with st.expander('Conferir modelos disponíveis', expanded=False):
        if isinstance(cadastro, pd.DataFrame):
            st.caption('Cadastro')
            _render_detection_badge('Modelo', cadastro, st.session_state.get(HOME_CADASTRO_MODEL_SOURCE_KEY))
            st.dataframe(cadastro.head(1).astype(str), use_container_width=True, height=120)
            st.caption(f'{len(cadastro.columns)} coluna(s): ' + ', '.join(map(str, cadastro.columns)))
        if isinstance(estoque, pd.DataFrame):
            st.caption('Estoque')
            _render_detection_badge('Modelo', estoque, st.session_state.get(HOME_ESTOQUE_MODEL_SOURCE_KEY))
            st.dataframe(estoque.head(1).astype(str), use_container_width=True, height=120)
            st.caption(f'{len(estoque.columns)} coluna(s): ' + ', '.join(map(str, estoque.columns)))


def render_home_bling_models() -> None:
    """Conteúdo da etapa Modelo de destino.

    O card visual externo fica no wizard para que explicação, upload, alerta
    e navegação fiquem no mesmo bloco, sem partes soltas na tela mobile.
    """
    ensure_default_home_models()

    st.markdown('#### Modelo de destino')
    st.caption(
        'Anexe o modelo que você quer preencher. O MapeiaAI detecta se parece cadastro, estoque, preços, multilojas ou personalizado.'
    )

    upload = render_model_upload_box(
        title='Modelos de destino',
        operation='cadastro',
        key='home_model_upload_bling',
        required_model=False,
        caption=None,
    )

    # Importante: nao usar upload.model_df como fallback de cadastro.
    # Quando o arquivo enviado e um modelo oficial de estoque, model_df tambem aponta
    # para estoque. O fallback antigo fazia o mesmo arquivo virar cadastro + estoque,
    # impedindo a escolha automatica de "Atualizar estoque" na etapa 2.
    cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else None
    estoque_model = upload.estoque_model_df if isinstance(upload.estoque_model_df, pd.DataFrame) else None

    if isinstance(cadastro_model, pd.DataFrame) or isinstance(estoque_model, pd.DataFrame):
        save_home_models(cadastro_model, estoque_model)

    _render_loaded_summary()
