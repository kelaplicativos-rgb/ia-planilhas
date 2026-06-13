from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.ui.home_download import (
    DESTINATION_MODEL_UPLOAD_BYTES_KEY,
    DESTINATION_MODEL_UPLOAD_NAME_KEY,
    DESTINATION_MODEL_UPLOAD_OBJECT_KEY,
    FINAL_DOWNLOAD_DF_SNAPSHOT_KEY,
    FINAL_DOWNLOAD_FILE_BYTES_KEY,
    FINAL_DOWNLOAD_FILE_NAME_KEY,
    FINAL_DOWNLOAD_MIME_KEY,
    FINAL_DOWNLOAD_OPERATION_KEY,
    FINAL_DOWNLOAD_RULES_SIGNATURE_KEY,
    FINAL_DOWNLOAD_SIGNATURE_KEY,
    FINAL_DOWNLOAD_WIDGET_KEY,
    df_signature,
    download_final,
)

PREVIEW_ROWS = 50
_PREVIEW_NESTING_KEY = '_bling_preview_nesting_level'

KIND_LABELS = {
    'id_produto': 'Identificador do produto',
    'codigo': 'Código/SKU',
    'gtin': 'GTIN/EAN',
    'descricao': 'Nome ou descrição',
    'deposito': 'Depósito',
    'estoque': 'Saldo/quantidade',
    'preco_custo': 'Preço de custo',
    'preco_unitario': 'Preço de venda',
    'observacao': 'Observação',
    'data': 'Data',
    'url': 'Link/URL',
    'nome_apoio': 'Nome de apoio',
    'imagem': 'Imagem',
    'marca': 'Marca',
    'categoria': 'Categoria',
    'ncm': 'NCM',
    'custom': 'Campo personalizado',
}


class _NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


@contextmanager
def _preview_context(label: str):
    level = int(st.session_state.get(_PREVIEW_NESTING_KEY, 0) or 0)
    st.session_state[_PREVIEW_NESTING_KEY] = level + 1
    opened_expander = False
    try:
        if level == 0:
            try:
                with st.expander(label, expanded=False):
                    opened_expander = True
                    yield
            except StreamlitAPIException as exc:
                if 'Expanders may not be nested' not in str(exc):
                    raise
                st.markdown(f'##### {label}')
                yield
        else:
            st.markdown(f'##### {label}')
            yield
    finally:
        current = int(st.session_state.get(_PREVIEW_NESTING_KEY, 1) or 1)
        st.session_state[_PREVIEW_NESTING_KEY] = max(0, current - 1)
        _ = opened_expander


@st.cache_data(show_spinner=False)
def _read_uploaded_file_cached(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    buffer = _NamedBytesIO(file_bytes, file_name)
    return read_uploaded_file(buffer)


def read_upload_fast(uploaded_file: Any | None) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    file_name = getattr(uploaded_file, 'name', 'arquivo')
    file_bytes = uploaded_file.getvalue()
    return _read_uploaded_file_cached(file_name, file_bytes).copy()


@st.cache_resource(show_spinner=False)
def load_cadastro_pipeline() -> Callable:
    from bling_app_zero.pipelines.cadastro_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_estoque_pipeline() -> Callable:
    from bling_app_zero.pipelines.estoque_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_site_pipeline() -> Callable:
    # BLINGFIX: reforça mídia e captura estoque quando o modelo solicitar.
    from bling_app_zero.pipelines.site_pipeline_stockfix import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_requested_columns_from_model() -> Callable:
    from bling_app_zero.flows.estoque_contract import requested_columns_from_model

    return requested_columns_from_model


def _kind_label(kind: str) -> str:
    return KIND_LABELS.get(str(kind or '').strip(), 'Campo personalizado')


def _preview_safe_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    out = df.head(PREVIEW_ROWS).copy()
    for column in out.columns:
        if out[column].dtype == 'object':
            out[column] = out[column].map(lambda value: '' if pd.isna(value) else str(value))
    return out


def _render_contract_body(columns: list[str]) -> None:
    contract = build_contract(columns)
    st.caption('Serão buscados somente estes campos. Se algum dado não existir na origem, ele ficará vazio.')
    st.dataframe(
        pd.DataFrame(
            [
                {
                    'Coluna solicitada': field.original,
                    'Tipo detectado': _kind_label(field.kind),
                    'Obrigatório': 'Sim' if field.required else 'Não',
                }
                for field in contract
            ]
        ),
        use_container_width=True,
        height=260,
    )


def show_contract(columns: list[str]) -> None:
    if not columns:
        return
    try:
        with st.expander('Campos que serão preenchidos', expanded=False):
            _render_contract_body(columns)
    except StreamlitAPIException as exc:
        if 'Expanders may not be nested' not in str(exc):
            raise
        st.markdown('##### Campos que serão preenchidos')
        _render_contract_body(columns)


def _render_mapping_body(mapping: dict[str, str]) -> None:
    st.dataframe(
        pd.DataFrame(
            [
                {'Campo do modelo': key, 'Origem usada': value or '(vazio)'}
                for key, value in mapping.items()
            ]
        ).astype(str),
        use_container_width=True,
        height=260,
    )


def show_mapping(mapping: dict[str, str], operation: str | None = None) -> None:
    if not mapping:
        return
    label = 'Como os campos foram preenchidos'
    if operation:
        label = '📄 MODELO FINAL · Como os campos foram preenchidos'
    try:
        with st.expander(label, expanded=False):
            _render_mapping_body(mapping)
    except StreamlitAPIException as exc:
        if 'Expanders may not be nested' not in str(exc):
            raise
        st.markdown(f'##### {label}')
        _render_mapping_body(mapping)


def _render_preview_body(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info('Sem dados para exibir ainda.')
        return

    total_rows = len(df)
    total_cols = len(df.columns)
    safe_df = _preview_safe_df(df)
    st.dataframe(safe_df, use_container_width=True, height=360)
    if total_rows > PREVIEW_ROWS:
        st.caption(f'Mostrando {PREVIEW_ROWS} de {total_rows} linha(s). Total: {total_cols} coluna(s).')
    else:
        st.caption(f'{total_rows} linha(s) × {total_cols} coluna(s)')


def preview_df(title: str, df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        label = title
    else:
        label = f'{title} · {len(df)} linha(s) × {len(df.columns)} coluna(s)'
    with _preview_context(label):
        _render_preview_body(df)


def render_download_section(df: pd.DataFrame, filename: str, *, operation: str | None = None) -> None:
    if df is None or df.empty:
        st.info('Nada para baixar ainda.')
        return
    download_final(df, filename, operation=operation)


def update_final_download_snapshot(df: pd.DataFrame, filename: str, mime: str, file_bytes: bytes, *, operation: str | None = None) -> None:
    st.session_state[FINAL_DOWNLOAD_DF_SNAPSHOT_KEY] = df
    st.session_state[FINAL_DOWNLOAD_FILE_NAME_KEY] = filename
    st.session_state[FINAL_DOWNLOAD_MIME_KEY] = mime
    st.session_state[FINAL_DOWNLOAD_FILE_BYTES_KEY] = file_bytes
    st.session_state[FINAL_DOWNLOAD_SIGNATURE_KEY] = df_signature(df)
    st.session_state[FINAL_DOWNLOAD_RULES_SIGNATURE_KEY] = ''
    st.session_state[FINAL_DOWNLOAD_OPERATION_KEY] = operation or ''
    st.session_state[FINAL_DOWNLOAD_WIDGET_KEY] = filename


def remember_destination_model(uploaded_file: Any | None) -> None:
    if uploaded_file is None:
        return
    try:
        st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = getattr(uploaded_file, 'name', '')
        st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = uploaded_file.getvalue()
        st.session_state[DESTINATION_MODEL_UPLOAD_OBJECT_KEY] = uploaded_file
    except Exception:
        pass


__all__ = [
    'load_cadastro_pipeline',
    'load_estoque_pipeline',
    'load_requested_columns_from_model',
    'load_site_pipeline',
    'preview_df',
    'read_upload_fast',
    'remember_destination_model',
    'render_download_section',
    'show_contract',
    'show_mapping',
    'update_final_download_snapshot',
]
