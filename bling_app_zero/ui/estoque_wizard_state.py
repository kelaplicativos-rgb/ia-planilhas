from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.home_shared import df_signature

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'
ESTOQUE_UPLOAD_KEY = 'estoque_wizard_upload'
ESTOQUE_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_MODELO_KEY = 'estoque_wizard_df_modelo'
ESTOQUE_DEPOSITO_KEY = 'estoque_nome_deposito'
ESTOQUE_DEPOSITO_SIGNATURE_KEY = 'estoque_deposito_signature_atual'
ESTOQUE_DEPOSITO_ALIAS_KEYS = [
    ESTOQUE_DEPOSITO_KEY,
    'deposito_estoque',
    'nome_deposito_estoque',
    'estoque_deposito',
    'nome_deposito',
]
BLING_IMPORTADOR_ESTOQUE_URL = 'https://www.bling.com.br/importador.saldos.estoque.php'

ESTOQUE_OUTPUT_KEYS = [
    'estoque_multi_outputs',
    'df_final_estoque',
    'mapping_estoque',
    'df_final_estoque_from_cadastro',
    'mapping_estoque_from_cadastro',
    'mapping_confidence_estoque_from_cadastro',
]


def valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def normalize_deposito(value: object) -> str:
    text = str(value or '').strip()
    if text.lower() in {'não definido', 'nao definido', 'undefined', 'none', 'null'}:
        return ''
    return text


def store_deposito_value(deposito: str, *, write_primary: bool = True) -> None:
    clean = normalize_deposito(deposito)
    if write_primary:
        st.session_state[ESTOQUE_DEPOSITO_KEY] = clean
    for key in ESTOQUE_DEPOSITO_ALIAS_KEYS:
        if key != ESTOQUE_DEPOSITO_KEY and (key in st.session_state or clean):
            st.session_state[key] = clean


def deposito_value() -> str:
    for key in ESTOQUE_DEPOSITO_ALIAS_KEYS:
        value = normalize_deposito(st.session_state.get(key))
        if value:
            if key != ESTOQUE_DEPOSITO_KEY and ESTOQUE_DEPOSITO_KEY not in st.session_state:
                store_deposito_value(value, write_primary=True)
            return value
    return ''


def valid_deposito() -> bool:
    return bool(deposito_value())


def is_site_origin() -> bool:
    return str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '').strip().lower() == 'site'


def current_source_signature(df_origem_site: pd.DataFrame | None, upload) -> str:
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        return 'site:' + df_signature(df_origem_site)
    files = source_files_from_upload(upload)
    names = [str(getattr(file, 'name', 'arquivo')) for file in files]
    sizes = [str(getattr(file, 'size', '')) for file in files]
    return 'upload:' + '|'.join(names + sizes)


def clear_estoque_outputs() -> None:
    for key in ESTOQUE_OUTPUT_KEYS:
        st.session_state.pop(key, None)


def clear_estoque_outputs_if_source_changed(df_origem_site: pd.DataFrame | None, upload) -> None:
    signature = current_source_signature(df_origem_site, upload)
    previous = st.session_state.get(ESTOQUE_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    clear_estoque_outputs()
    st.session_state[ESTOQUE_SOURCE_SIGNATURE_KEY] = signature


def clear_estoque_outputs_if_deposito_changed(deposito: str) -> None:
    signature = normalize_deposito(deposito)
    previous = st.session_state.get(ESTOQUE_DEPOSITO_SIGNATURE_KEY)
    if previous is None:
        st.session_state[ESTOQUE_DEPOSITO_SIGNATURE_KEY] = signature
        return
    if previous == signature:
        return
    clear_estoque_outputs()
    st.session_state[ESTOQUE_DEPOSITO_SIGNATURE_KEY] = signature


def store_estoque_context(upload, df_origem_site: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    st.session_state[ESTOQUE_UPLOAD_KEY] = upload
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.session_state[ESTOQUE_ORIGEM_SITE_KEY] = df_origem_site
    else:
        st.session_state.pop(ESTOQUE_ORIGEM_SITE_KEY, None)
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        st.session_state[ESTOQUE_MODELO_KEY] = df_modelo
    else:
        st.session_state.pop(ESTOQUE_MODELO_KEY, None)


def has_stock_source(upload=None, df_site=None) -> bool:
    current_upload = st.session_state.get(ESTOQUE_UPLOAD_KEY) if upload is None else upload
    current_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY) if df_site is None else df_site
    has_site = isinstance(current_site, pd.DataFrame) and not current_site.empty
    has_upload = bool(current_upload is not None and source_files_from_upload(current_upload))
    return has_site or has_upload


def estoque_context_ready() -> bool:
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    return has_stock_source() and valid_model(df_modelo) and valid_deposito()


def generated_output_ready() -> bool:
    outputs = st.session_state.get('estoque_multi_outputs')
    if isinstance(outputs, list) and outputs:
        return True
    df_final = st.session_state.get('df_final_estoque')
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def estoque_output_ready() -> bool:
    return generated_output_ready()


def current_stock_source() -> tuple[pd.DataFrame | None, str]:
    df_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        return df_site, 'Origem criada pelo site'

    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    files = source_files_from_upload(upload)
    if not files:
        return None, ''
    if len(files) > 1:
        st.warning('Mapeamento manual de estoque usa uma origem por vez. Para múltiplos arquivos, gere um CSV por arquivo.')
    first_file = files[0]
    df_file = safe_read_source(first_file)
    if isinstance(df_file, pd.DataFrame) and not df_file.empty:
        return df_file, file_name(first_file)
    return None, ''


def sync_manual_stock_output(name: str) -> bool:
    df_final = st.session_state.get('df_final_estoque_from_cadastro')
    mapping = st.session_state.get('mapping_estoque_from_cadastro', {})
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return False
    result = {'index': 1, 'name': name or 'Origem de estoque', 'df_final': df_final, 'mapping': mapping if isinstance(mapping, dict) else {}}
    st.session_state['estoque_multi_outputs'] = [result]
    st.session_state['df_final_estoque'] = df_final
    st.session_state['mapping_estoque'] = result['mapping']
    return True


def build_stock_outputs_if_possible() -> bool:
    if generated_output_ready():
        return True
    return sync_manual_stock_output('Origem de estoque')


__all__ = [
    'BLING_IMPORTADOR_ESTOQUE_URL',
    'ESTOQUE_DEPOSITO_KEY',
    'ESTOQUE_MODELO_KEY',
    'build_stock_outputs_if_possible',
    'clear_estoque_outputs_if_deposito_changed',
    'clear_estoque_outputs_if_source_changed',
    'current_stock_source',
    'deposito_value',
    'estoque_context_ready',
    'estoque_output_ready',
    'is_site_origin',
    'normalize_deposito',
    'store_deposito_value',
    'store_estoque_context',
    'sync_manual_stock_output',
    'valid_model',
]
