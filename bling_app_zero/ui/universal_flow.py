from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import build_universal_contract, validate_universal_output

UNIVERSAL_MODEL_KEY = 'mapeiaai_universal_model_df'
UNIVERSAL_SOURCE_KEY = 'mapeiaai_universal_source_df'
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
UNIVERSAL_SIGNATURE_KEY = 'mapeiaai_universal_signature'
UNIVERSAL_ENGINE_KEY = 'mapeiaai_universal_mapping_engine'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'
EMPTY_OPTION = '(deixar vazio)'
SUPPORTED_UPLOAD_LABEL = 'Formatos aceitos: XLSX, XLS, CSV, XLSM, XLSB, XML, HTML, MHTML e PDF. No celular, o seletor fica livre para evitar bloqueio falso do Android.'


def _read_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        df = read_uploaded_file(uploaded_file).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo: {exc}')
        return None
    if not isinstance(df, pd.DataFrame) or df.empty or not len(df.columns):
        st.warning('Arquivo recebido, mas não encontrei uma tabela válida. Confira se o arquivo está em XLSX, XLS, CSV, XML, HTML, MHTML ou PDF.')
        return None
    return df


def _store_df(key: str, df: pd.DataFrame | None) -> None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        st.session_state[key] = df.copy().fillna('')


def _current_df(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else None


def _df_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame):
        return 'none'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample_hash = '0'
    if not df.empty:
        sample = pd.util.hash_pandas_object(df.head(80).fillna('').astype(str), index=True).sum()
        sample_hash = str(sample)
    raw = f'{shape}:{columns}:{sample_hash}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _flow_signature(model: pd.DataFrame, source: pd.DataFrame) -> str:
    return f'{_df_signature(model)}:{_df_signature(source)}'


def _short_hash(value: str, size: int = 8) -> str:
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()[:size]


def _reset_universal_state_if_changed(model: pd.DataFrame, source: pd.DataFrame) -> str:
    signature = _flow_signature(model, source)
    previous = str(st.session_state.get(UNIVERSAL_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)
        st.session_state.pop(UNIVERSAL_OUTPUT_KEY, None)
        st.session_state.pop(UNIVERSAL_ENGINE_KEY, None)
        for key in list(st.session_state.keys()):
            if str(key).startswith('mapeiaai_universal_map_'):
                st.session_state.pop(key, None)
        add_audit_event(
            'universal_flow_state_reset_by_signature_change',
            area='UNIVERSAL',
            details={'previous': previous, 'current': signature, 'responsible_file': RESPONSIBLE_FILE},
        )
    st.session_state[UNIVERSAL_SIGNATURE_KEY] = signature
    return signature


def _render_model_step() -> pd.DataFrame | None:
    st.markdown('### 1. Contrato final')
    model = _current_df(UNIVERSAL_MODEL_KEY)
    if isinstance(model, pd.DataFrame):
        st.success('Contrato final carregado pela primeira tela.')
        st.caption('A planilha final seguirá exatamente essas colunas e essa ordem. Não há detecção de sistema/fornecedor nesta etapa.')
        st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
        st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
        return model

    st.caption('Anexe a planilha exatamente no formato que você quer receber no final.')
    st.caption(SUPPORTED_UPLOAD_LABEL)
    uploaded = st.file_uploader(
        'Contrato final da planilha',
        type=None,
        key='mapeiaai_universal_model_upload',
        help='O filtro de tipo fica aberto para evitar que o Android bloqueie CSV/planilhas válidas no seletor de arquivos.',
    )
    df_model = _read_upload(uploaded)
    if isinstance(df_model, pd.DataFrame):
        _store_df(UNIVERSAL_MODEL_KEY, df_model)

    model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.info('Envie a planilha/contrato final para começar.')
        return None

    st.success('Contrato final recebido.')
    st.caption('A planilha final seguirá exatamente essas colunas e essa ordem.')
    st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
    st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
    return model


def _render_source_step() -> pd.DataFrame | None:
    st.markdown('### 2. Origem dos dados')
    st.caption('Anexe a origem dos dados: fornecedor, CSV, planilha, XML, HTML, MHTML ou PDF.')
    st.caption(SUPPORTED_UPLOAD_LABEL)
    uploaded = st.file_uploader(
        'Origem dos dados',
        type=None,
        key='mapeiaai_universal_source_upload',
        help='O filtro de tipo fica aberto para evitar que o Android bloqueie CSV/planilhas válidas no seletor de arquivos.',
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


def _suggest_mapping(source: pd.DataFrame, model: pd.DataFrame) -> tuple[dict[str, str], str]:
    result = suggest_mapping_with_openai(source, model, operation='universal')
    data = result.data if isinstance(result.data, dict) else {}
    mapping = data.get('mapping')
    engine = str(data.get('engine') or 'local')
    safe_mapping = {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}
    return safe_mapping, engine


def _mapping_widget_key(signature: str, index: int, target_name: str) -> str:
    return f'mapeiaai_universal_map_{index}_{_short_hash(signature + target_name)}'


def _render_mapping_step(source: pd.DataFrame, model: pd.DataFrame, signature: str) -> dict[str, str]:
    st.markdown('### 3. Mapeamento por contrato')
    st.caption('Cada coluna do contrato final aponta para uma coluna da origem. O que não existir fica vazio.')

    if UNIVERSAL_MAPPING_KEY not in st.session_state:
        suggested, engine = _suggest_mapping(source, model)
        st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
        st.session_state[UNIVERSAL_ENGINE_KEY] = engine

    engine = str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or 'local')
    st.caption('Motor de sugestão: OpenAI validada' if engine == 'openai_validated' else 'Motor de sugestão: local seguro')

    current = dict(st.session_state.get(UNIVERSAL_MAPPING_KEY) or {})
    source_options = [EMPTY_OPTION] + [str(column) for column in source.columns]
    edited: dict[str, str] = {}

    for index, target in enumerate(model.columns):
        target_name = str(target)
        current_value = current.get(target_name, '')
        default_index = source_options.index(current_value) if current_value in source_options else 0
        selected = st.selectbox(
            target_name,
            source_options,
            index=default_index,
            key=_mapping_widget_key(signature, index, target_name),
        )
        edited[target_name] = '' if selected == EMPTY_OPTION else selected

    st.session_state[UNIVERSAL_MAPPING_KEY] = edited
    return edited


def _render_preview_and_download(source: pd.DataFrame, model: pd.DataFrame, mapping: dict[str, str]) -> None:
    st.markdown('### 4. Preview e download fiel')
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

    st.success('Planilha final fiel ao contrato anexado: mesmas colunas, mesma ordem, sem extras.')
    st.dataframe(output.head(50).astype(str), use_container_width=True, height=320)
    st.download_button(
        '⬇️ Baixar planilha final mapeada',
        data=final_csv_bytes(output, operation='universal', run_download_features=True),
        file_name='mapeiaai_planilha_final_mapeada.csv',
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
    st.markdown('## Mapear planilha por contrato')
    st.caption('O anexo define a saída. A origem fornece os dados. A IA real ajuda a correlacionar cabeçalhos e conteúdo.')

    model = _render_model_step()
    if not isinstance(model, pd.DataFrame):
        return
    source = _render_source_step()
    if not isinstance(source, pd.DataFrame):
        return
    signature = _reset_universal_state_if_changed(model, source)
    mapping = _render_mapping_step(source, model, signature)
    _render_preview_and_download(source, model, mapping)


__all__ = ['render_universal_flow']
