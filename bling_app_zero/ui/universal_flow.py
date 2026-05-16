from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_mapping_suggester import suggest_mapping
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.universal.model_detector import detect_model_type
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import build_universal_contract, validate_universal_output

UNIVERSAL_MODEL_KEY = 'mapeiaai_universal_model_df'
UNIVERSAL_SOURCE_KEY = 'mapeiaai_universal_source_df'
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'


def _read_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        return read_uploaded_file(uploaded_file).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo: {exc}')
        return None


def _store_df(key: str, df: pd.DataFrame | None) -> None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        st.session_state[key] = df.copy().fillna('')


def _current_df(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else None


def _render_model_step() -> pd.DataFrame | None:
    st.markdown('### 1. Modelo de destino')
    st.caption('Anexe a planilha exatamente no formato que você quer receber no final.')
    uploaded = st.file_uploader(
        'Modelo de destino',
        type=['xlsx', 'xls', 'csv', 'xlsm', 'xlsb'],
        key='mapeiaai_universal_model_upload',
    )
    df_model = _read_upload(uploaded)
    if isinstance(df_model, pd.DataFrame):
        _store_df(UNIVERSAL_MODEL_KEY, df_model)

    model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.info('Envie o modelo de destino para começar.')
        return None

    detection = detect_model_type(model)
    st.success(f'Tipo detectado: {detection.model_type} · confiança {round(detection.confidence * 100)}%')
    st.caption(detection.reason)
    st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
    st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
    return model


def _render_source_step() -> pd.DataFrame | None:
    st.markdown('### 2. Origem dos dados')
    st.caption('Anexe a planilha, CSV ou arquivo do fornecedor que contém os dados brutos.')
    uploaded = st.file_uploader(
        'Origem dos dados',
        type=['xlsx', 'xls', 'csv', 'xlsm', 'xlsb', 'xml', 'html', 'htm'],
        key='mapeiaai_universal_source_upload',
    )
    df_source = _read_upload(uploaded)
    if isinstance(df_source, pd.DataFrame):
        _store_df(UNIVERSAL_SOURCE_KEY, df_source)

    source = _current_df(UNIVERSAL_SOURCE_KEY)
    if not isinstance(source, pd.DataFrame):
        st.info('Envie a origem dos dados para liberar o mapeamento.')
        return None

    st.success(f'Origem carregada: {len(source)} linha(s) × {len(source.columns)} coluna(s).')
    with st.expander('Ver origem', expanded=False):
        st.dataframe(source.head(20).astype(str), use_container_width=True, height=260)
    return source


def _suggest_mapping(source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
    result = suggest_mapping(source, model)
    data = result.data if isinstance(result.data, dict) else {}
    mapping = data.get('mapping')
    return {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}


def _render_mapping_step(source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
    st.markdown('### 3. Mapeamento universal')
    st.caption('Cada campo do modelo deve apontar para uma coluna da origem. Campo sem dado fica vazio na planilha final.')

    if UNIVERSAL_MAPPING_KEY not in st.session_state:
        st.session_state[UNIVERSAL_MAPPING_KEY] = _suggest_mapping(source, model)

    current = dict(st.session_state.get(UNIVERSAL_MAPPING_KEY) or {})
    source_options = ['(deixar vazio)'] + [str(column) for column in source.columns]
    edited: dict[str, str] = {}

    for target in model.columns:
        target_name = str(target)
        current_value = current.get(target_name, '')
        default_index = source_options.index(current_value) if current_value in source_options else 0
        selected = st.selectbox(
            target_name,
            source_options,
            index=default_index,
            key=f'mapeiaai_universal_map_{target_name}',
        )
        edited[target_name] = '' if selected == '(deixar vazio)' else selected

    st.session_state[UNIVERSAL_MAPPING_KEY] = edited
    return edited


def _render_preview_and_download(source: pd.DataFrame, model: pd.DataFrame, mapping: dict[str, str]) -> None:
    st.markdown('### 4. Preview e planilha final')
    contract = build_universal_contract(model)
    if source.empty:
        output = empty_universal_output(model, rows=0)
    else:
        output = build_universal_output(source, model, mapping)
    errors = validate_universal_output(output, contract)
    st.session_state[UNIVERSAL_OUTPUT_KEY] = output

    if errors:
        for error in errors:
            st.error(error)
        return

    st.success('Planilha final idêntica ao modelo de destino em colunas e ordem.')
    st.dataframe(output.head(50).astype(str), use_container_width=True, height=320)
    st.download_button(
        '⬇️ Baixar planilha final universal',
        data=final_csv_bytes(output, operation='universal', run_download_features=True),
        file_name='mapeiaai_planilha_final_universal.csv',
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key='mapeiaai_universal_download',
    )
    add_audit_event(
        'universal_flow_preview_rendered',
        area='UNIVERSAL',
        details={'rows': int(len(output)), 'columns': int(len(output.columns)), 'responsible_file': RESPONSIBLE_FILE},
    )


def render_universal_flow() -> None:
    st.markdown('## Modelo universal')
    st.caption('Qualquer modelo anexado vira o formato final. Cadastro, estoque, preços e multilojas são apenas tipos detectados.')

    model = _render_model_step()
    if not isinstance(model, pd.DataFrame):
        return
    source = _render_source_step()
    if not isinstance(source, pd.DataFrame):
        return
    mapping = _render_mapping_step(source, model)
    _render_preview_and_download(source, model, mapping)


__all__ = ['render_universal_flow']
