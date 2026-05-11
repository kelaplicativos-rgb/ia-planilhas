from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.ui.model_upload import render_model_upload_box

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
HOME_HAS_MODELS_KEY = 'home_modelos_bling_ok'
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


def _save_model(key: str, df: pd.DataFrame | None, aliases: list[str]) -> None:
    copied = _copy_df(df)
    if copied is None:
        return
    st.session_state[key] = copied.copy().fillna('')
    for alias in aliases:
        st.session_state[alias] = copied.copy().fillna('')


def _forget_model(key: str, aliases: list[str]) -> None:
    st.session_state.pop(key, None)
    for alias in aliases:
        st.session_state.pop(alias, None)


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


def save_home_models(
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
) -> None:
    cadastro = _copy_df(cadastro_model_df)
    estoque = _copy_df(estoque_model_df)

    if cadastro is not None:
        _save_model(HOME_CADASTRO_MODEL_KEY, cadastro, GLOBAL_CADASTRO_MODEL_KEYS)
    else:
        _forget_model(HOME_CADASTRO_MODEL_KEY, GLOBAL_CADASTRO_MODEL_KEYS)

    if estoque is not None:
        _save_model(HOME_ESTOQUE_MODEL_KEY, estoque, GLOBAL_ESTOQUE_MODEL_KEYS)
    else:
        _forget_model(HOME_ESTOQUE_MODEL_KEY, GLOBAL_ESTOQUE_MODEL_KEYS)

    _sync_detected_operation(cadastro, estoque)
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


def _render_loaded_summary() -> None:
    cadastro = get_home_cadastro_model()
    estoque = get_home_estoque_model()
    parts: list[str] = []
    if isinstance(cadastro, pd.DataFrame):
        parts.append('cadastro')
    if isinstance(estoque, pd.DataFrame):
        parts.append('estoque')
    if parts:
        st.success('Modelos carregados: ' + ' + '.join(parts))


def _open_model_card() -> None:
    kicker = html.escape('Etapa 1')
    title = html.escape('Modelo do Bling')
    text = html.escape(
        'Envie o modelo de cadastro, estoque ou ambos. O sistema usa esse arquivo como contrato das colunas que podem ser preenchidas.'
    )
    st.markdown(
        f"""
        <section class="bling-flow-card bling-model-step-card">
            <div class="bling-flow-card-kicker">{kicker}</div>
            <h2 class="bling-flow-card-title">{title}</h2>
            <p class="bling-flow-card-text">{text}</p>
            <div class="bling-model-upload-anchor"></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_home_bling_models() -> None:
    """Renderiza a etapa 1 como um único bloco visual."""
    _open_model_card()

    upload = render_model_upload_box(
        title='Modelos do Bling',
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
