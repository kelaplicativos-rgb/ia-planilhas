from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.features_runtime.router import active_contract
from bling_app_zero.pipelines.site_pipeline import run_pipeline as run_site_pipeline
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.shared_calculator import render_shared_calculator
from bling_app_zero.ui.shared_final_csv import render_shared_final_csv
from bling_app_zero.ui.shared_mapping import clear_shared_mapping_widgets, render_shared_contract_mapping, suggest_shared_mapping

UNIVERSAL_MODEL_KEY = 'mapeiaai_universal_model_df'
UNIVERSAL_SOURCE_KEY = 'mapeiaai_universal_source_df'
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
UNIVERSAL_SIGNATURE_KEY = 'mapeiaai_universal_signature'
UNIVERSAL_ENGINE_KEY = 'mapeiaai_universal_mapping_engine'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'
SOURCE_MODE_UPLOAD = 'Anexar arquivo de origem'
SOURCE_MODE_SITE = 'Buscar produtos por site'
SUPPORTED_UPLOAD_LABEL = 'Formatos aceitos: XLSX, XLS, CSV, XLSM, XLSB, XML, HTML, MHTML e PDF. No celular, o seletor fica livre para evitar bloqueio falso do Android.'


def _is_universal_csv_context() -> bool:
    contract = active_contract()
    return contract.key == 'universal_csv' or (contract.mode == 'csv' and contract.operation == 'universal')


def _render_contract_guard() -> bool:
    if _is_universal_csv_context():
        return True
    contract = active_contract()
    st.warning('Este fluxo é exclusivo para Mapear planilha por contrato / Universal CSV.')
    st.caption(f'Contrato ativo atual: {contract.key}. Use o fluxo principal para {contract.label}.')
    add_audit_event(
        'universal_flow_blocked_outside_universal_csv',
        area='UNIVERSAL',
        status='BLOQUEADO',
        details={'active_contract': contract.key, 'operation': contract.operation, 'mode': contract.mode, 'responsible_file': RESPONSIBLE_FILE},
    )
    return False


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


def _reset_universal_state_if_changed(model: pd.DataFrame, source: pd.DataFrame) -> str:
    signature = _flow_signature(model, source)
    previous = str(st.session_state.get(UNIVERSAL_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)
        st.session_state.pop(UNIVERSAL_OUTPUT_KEY, None)
        st.session_state.pop(UNIVERSAL_ENGINE_KEY, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
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


def _progress_callback(progress_bar, status_box):
    def _callback(info: dict) -> None:
        progress = float(info.get('progress') or 0.0)
        stage = str(info.get('stage') or 'Processando')
        message = str(info.get('message') or '')
        progress_bar.progress(max(0.0, min(1.0, progress)), text=stage)
        status_box.caption(message)
    return _callback


def _render_source_upload() -> pd.DataFrame | None:
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
    return _current_df(UNIVERSAL_SOURCE_KEY)


def _render_source_site(model: pd.DataFrame) -> pd.DataFrame | None:
    st.caption('Cole links de produtos, categorias ou buscas. O motor de site captura dados e monta a origem para o mapeamento.')
    raw_urls = st.text_area(
        'Links para buscar produtos por site',
        height=130,
        key='mapeiaai_universal_site_urls',
        placeholder='https://fornecedor.com/produto-1\nhttps://fornecedor.com/categoria/acessorios',
    )
    all_products = st.checkbox('Buscar todos os produtos encontrados', value=True, key='mapeiaai_universal_site_all_products')
    if st.button('🔎 Buscar produtos por site', use_container_width=True, key='mapeiaai_universal_run_site'):
        if not str(raw_urls or '').strip():
            st.warning('Informe pelo menos um link para buscar por site.')
        else:
            progress_bar = st.progress(0, text='Preparando busca por site...')
            status_box = st.empty()
            try:
                df_site = run_site_pipeline(
                    str(raw_urls),
                    requested_columns=[str(column) for column in model.columns],
                    all_products=bool(all_products),
                    operation='universal',
                    progress_callback=_progress_callback(progress_bar, status_box),
                )
                _store_df(UNIVERSAL_SOURCE_KEY, df_site)
                add_audit_event(
                    'universal_site_source_loaded',
                    area='UNIVERSAL',
                    details={'rows': int(len(df_site)), 'columns': int(len(df_site.columns)), 'operation': 'universal', 'responsible_file': RESPONSIBLE_FILE},
                )
                st.success(f'Busca por site concluída: {len(df_site)} linha(s).')
            except Exception as exc:
                st.error(f'Falha ao buscar produtos por site: {exc}')
    return _current_df(UNIVERSAL_SOURCE_KEY)


def _render_source_step(model: pd.DataFrame) -> pd.DataFrame | None:
    st.markdown('### 2. Origem dos dados')
    source_mode = st.radio(
        'Como quer trazer os dados da origem?',
        [SOURCE_MODE_SITE, SOURCE_MODE_UPLOAD],
        horizontal=False,
        key='mapeiaai_universal_source_mode',
    )
    source = _render_source_site(model) if source_mode == SOURCE_MODE_SITE else _render_source_upload()
    if not isinstance(source, pd.DataFrame):
        st.info('Carregue a origem dos dados para liberar IA, cálculo, mapeamento, preview e download.')
        return None

    st.success(f'Origem carregada: {len(source)} linha(s) × {len(source.columns)} coluna(s).')
    with st.expander('Ver origem carregada', expanded=False):
        st.dataframe(source.head(30).astype(str), use_container_width=True, height=280)
    return source


def _render_ai_tools(source: pd.DataFrame, model: pd.DataFrame) -> None:
    st.markdown('### 3. Recursos IA Real')
    st.caption('A IA real pode sugerir mapeamento, corrigir ortografia e preparar títulos/descrições sem alterar o contrato final.')
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🤖 Regerar sugestão de mapeamento com IA', use_container_width=True, key='mapeiaai_universal_regen_ai_mapping'):
            suggested, engine = suggest_shared_mapping(source, model, operation='universal')
            st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
            st.session_state[UNIVERSAL_ENGINE_KEY] = engine
            clear_shared_mapping_widgets('mapeiaai_universal')
            st.success('Sugestões de mapeamento atualizadas.')
            safe_rerun('universal_ai_mapping_regenerated')
    with col2:
        st.caption('Regras ativas: título até 59 caracteres, texto fiel aos dados e descrição complementar persuasiva quando houver coluna compatível.')


def render_universal_flow() -> None:
    if not _render_contract_guard():
        return

    st.markdown('## Mapear planilha por contrato')
    st.caption('O anexo define a saída. A origem fornece os dados. A IA real ajuda a correlacionar cabeçalhos e conteúdo.')

    model = _render_model_step()
    if not isinstance(model, pd.DataFrame):
        return
    source = _render_source_step(model)
    if not isinstance(source, pd.DataFrame):
        return
    source_with_price = render_shared_calculator(source, key_prefix='mapeiaai_universal')
    signature = _reset_universal_state_if_changed(model, source_with_price)
    _render_ai_tools(source_with_price, model)
    mapping = render_shared_contract_mapping(
        source_with_price,
        model,
        signature=signature,
        mapping_state_key=UNIVERSAL_MAPPING_KEY,
        engine_state_key=UNIVERSAL_ENGINE_KEY,
        key_prefix='mapeiaai_universal',
    )
    output = render_shared_final_csv(
        source_with_price,
        model,
        mapping,
        key_prefix='mapeiaai_universal',
        file_name='mapeiaai_planilha_final_mapeada.csv',
    )
    if isinstance(output, pd.DataFrame):
        st.session_state[UNIVERSAL_OUTPUT_KEY] = output


__all__ = ['render_universal_flow']
