from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import filename_for_operation, to_bling_csv_bytes
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.validators import validate_final_df

PREVIEW_ROWS = 50
_PREVIEW_NESTING_KEY = '_bling_preview_nesting_level'


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
def load_apply_pricing() -> Callable:
    from bling_app_zero.core.pricing import apply_pricing

    return apply_pricing


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
    from bling_app_zero.pipelines.site_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_requested_columns_from_model() -> Callable:
    from bling_app_zero.flows.estoque_contract import requested_columns_from_model

    return requested_columns_from_model


def df_signature(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


@st.cache_data(show_spinner=False)
def _csv_bytes_cached(df: pd.DataFrame, operation: str, signature: str) -> bytes:
    _ = operation
    _ = signature
    return to_bling_csv_bytes(df)


def _render_contract_body(columns: list[str]) -> None:
    contract = build_contract(columns)
    st.caption('Serão buscados somente estes campos. Se algum dado não existir no site, ele ficará vazio.')
    st.dataframe(
        pd.DataFrame([
            {
                'Coluna solicitada': field.original,
                'Tipo detectado': field.kind,
                'Obrigatório': 'Sim' if field.required else 'Não',
            }
            for field in contract
        ]),
        use_container_width=True,
        height=260,
    )


def show_contract(columns: list[str]) -> None:
    if not columns:
        return
    try:
        with st.expander('Campos que serão buscados', expanded=False):
            _render_contract_body(columns)
    except StreamlitAPIException as exc:
        if 'Expanders may not be nested' not in str(exc):
            raise
        st.markdown('##### Campos que serão buscados')
        _render_contract_body(columns)


def show_mapping(mapping: dict[str, str]) -> None:
    if not mapping:
        return
    with st.expander('Como os campos foram preenchidos', expanded=False):
        st.dataframe(
            pd.DataFrame([
                {'Campo no Bling': key, 'Origem usada': value or '(vazio)'}
                for key, value in mapping.items()
            ]),
            use_container_width=True,
            height=260,
        )


def download_final(df: pd.DataFrame, operation: str, key: str) -> None:
    if df is None or df.empty:
        st.warning('Ainda não há dados finais para baixar.')
        return

    errors = validate_final_df(df, operation)
    if errors:
        with st.expander('Conferência antes do download', expanded=True):
            for error in errors:
                st.warning(error)

    signature = df_signature(df)
    csv_bytes = _csv_bytes_cached(df.copy(), operation, signature)

    st.download_button(
        '⬇️ Baixar CSV pronto para o Bling',
        data=csv_bytes,
        file_name=filename_for_operation(operation),
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'download_{key}_{signature}',
    )


def _render_preview_body(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info('Sem dados para exibir ainda.')
        return

    total_rows = len(df)
    total_cols = len(df.columns)
    st.dataframe(df.head(PREVIEW_ROWS), use_container_width=True, height=360)
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
