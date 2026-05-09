from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.layout import render_compact_note
from bling_app_zero.ui.model_upload import render_model_upload_box

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
HOME_HAS_MODELS_KEY = 'home_modelos_bling_ok'

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


def save_home_models(
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
) -> None:
    _save_model(HOME_CADASTRO_MODEL_KEY, cadastro_model_df, GLOBAL_CADASTRO_MODEL_KEYS)
    _save_model(HOME_ESTOQUE_MODEL_KEY, estoque_model_df, GLOBAL_ESTOQUE_MODEL_KEYS)
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


def _render_instructions() -> None:
    with st.expander('Onde encontro o modelo no Bling?', expanded=False):
        st.markdown(
            """
            1. Entre no **Bling**.
            2. Abra a área de **Produtos**.
            3. Vá em **Importar / Exportar**.
            4. Baixe o modelo de **Cadastro de produtos** ou de **Atualização de estoque**.
            5. Volte aqui e envie o arquivo.
            """
        )
        st.caption('Use o modelo oficial para o sistema preencher as colunas certas e evitar erro na importação.')


def _render_loaded_summary() -> None:
    cadastro = get_home_cadastro_model()
    estoque = get_home_estoque_model()
    parts: list[str] = []
    if isinstance(cadastro, pd.DataFrame):
        parts.append(f'Cadastro: {len(cadastro.columns)} coluna(s)')
    if isinstance(estoque, pd.DataFrame):
        parts.append(f'Estoque: {len(estoque.columns)} coluna(s)')
    if parts:
        st.success('Modelo pronto para uso · ' + ' · '.join(parts))


def render_home_bling_models() -> None:
    st.markdown('### 1. Modelos do Bling')
    st.caption('Envie o modelo oficial uma vez. Depois o sistema usa essa base em todos os próximos passos.')
    render_compact_note('Quanto melhor o modelo, mais limpo sai o CSV final para importar no Bling.')
    _render_instructions()

    upload = render_model_upload_box(
        title='Enviar modelo oficial',
        operation='cadastro',
        key='home_model_upload_bling',
        required_model=False,
        caption='Pode enviar o modelo de cadastro, o modelo de estoque ou os dois juntos.',
    )

    cadastro_model = upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else upload.model_df
    estoque_model = upload.estoque_model_df
    if isinstance(cadastro_model, pd.DataFrame) or isinstance(estoque_model, pd.DataFrame):
        save_home_models(cadastro_model, estoque_model)

    _render_loaded_summary()
