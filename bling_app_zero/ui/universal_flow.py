from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.ai.ai_text_rules import clean_title_to_limit, is_description_column, is_title_column
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.pipelines.site_pipeline import run_pipeline as run_site_pipeline
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import build_universal_contract, validate_universal_output

UNIVERSAL_MODEL_KEY = 'mapeiaai_universal_model_df'
UNIVERSAL_SOURCE_KEY = 'mapeiaai_universal_source_df'
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
UNIVERSAL_SIGNATURE_KEY = 'mapeiaai_universal_signature'
UNIVERSAL_ENGINE_KEY = 'mapeiaai_universal_mapping_engine'
UNIVERSAL_PRICE_COLUMN_KEY = 'mapeiaai_universal_price_column'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'
EMPTY_OPTION = '(deixar vazio)'
SOURCE_MODE_UPLOAD = 'Anexar arquivo de origem'
SOURCE_MODE_SITE = 'Buscar produtos por site'
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


def _parse_decimal(value: object) -> Decimal | None:
    text = str(value or '').strip()
    if not text:
        return None
    text = re.sub(r'[^0-9,.-]+', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _format_money(value: Decimal) -> str:
    return f'{value.quantize(Decimal("0.01"))}'.replace('.', ',')


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in df.columns:
        sample = df[column].head(25).map(_parse_decimal)
        if sample.notna().sum() >= max(1, min(3, len(sample))):
            columns.append(str(column))
    return columns


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
                    operation='cadastro',
                    progress_callback=_progress_callback(progress_bar, status_box),
                )
                _store_df(UNIVERSAL_SOURCE_KEY, df_site)
                add_audit_event(
                    'universal_site_source_loaded',
                    area='UNIVERSAL',
                    details={'rows': int(len(df_site)), 'columns': int(len(df_site.columns)), 'responsible_file': RESPONSIBLE_FILE},
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


def _suggest_mapping(source: pd.DataFrame, model: pd.DataFrame) -> tuple[dict[str, str], str]:
    result = suggest_mapping_with_openai(source, model, operation='universal')
    data = result.data if isinstance(result.data, dict) else {}
    mapping = data.get('mapping')
    engine = str(data.get('engine') or 'local')
    safe_mapping = {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}
    return safe_mapping, engine


def _mapping_widget_key(signature: str, index: int, target_name: str) -> str:
    return f'mapeiaai_universal_map_{index}_{_short_hash(signature + target_name)}'


def _confidence_flag(target: str, source_column: str, source: pd.DataFrame) -> str:
    if not source_column:
        return '🔴 vazio'
    target_key = re.sub(r'[^a-z0-9]+', '', target.lower())
    source_key = re.sub(r'[^a-z0-9]+', '', source_column.lower())
    if target_key and (target_key == source_key or target_key in source_key or source_key in target_key):
        return '🟢 alto'
    if source_column in source.columns and source[source_column].astype(str).str.strip().ne('').any():
        return '🟡 revisar'
    return '🔴 vazio'


def _render_ai_tools(source: pd.DataFrame, model: pd.DataFrame) -> None:
    st.markdown('### 3. Recursos IA Real')
    st.caption('A IA real pode sugerir mapeamento, corrigir ortografia e preparar títulos/descrições sem alterar o contrato final.')
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🤖 Regerar sugestão de mapeamento com IA', use_container_width=True, key='mapeiaai_universal_regen_ai_mapping'):
            suggested, engine = _suggest_mapping(source, model)
            st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
            st.session_state[UNIVERSAL_ENGINE_KEY] = engine
            for key in list(st.session_state.keys()):
                if str(key).startswith('mapeiaai_universal_map_'):
                    st.session_state.pop(key, None)
            st.success('Sugestões de mapeamento atualizadas.')
            st.rerun()
    with col2:
        st.caption('Regras ativas: título até 59 caracteres, texto fiel aos dados e descrição complementar persuasiva quando houver coluna compatível.')


def _render_price_calculator(source: pd.DataFrame) -> pd.DataFrame:
    st.markdown('### 4. Calculadora marketplace opcional')
    with st.expander('Aplicar cálculo marketplace na origem antes do mapeamento', expanded=False):
        numeric_columns = _numeric_columns(source)
        if not numeric_columns:
            st.info('Não encontrei colunas numéricas suficientes para cálculo automático.')
            return source
        enabled = st.checkbox('Usar cálculo marketplace', value=False, key='mapeiaai_universal_use_price_calc')
        base_column = st.selectbox('Coluna base de preço/custo', numeric_columns, key='mapeiaai_universal_price_base_column')
        target_name = st.text_input('Nome da coluna calculada', value='Preço calculado marketplace', key='mapeiaai_universal_price_output_name')
        margem = Decimal(str(st.number_input('Margem (%)', min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key='mapeiaai_universal_margin') or 0))
        taxa = Decimal(str(st.number_input('Taxas/marketplace (%)', min_value=0.0, max_value=1000.0, value=18.0, step=1.0, key='mapeiaai_universal_fee') or 0))
        fixo = Decimal(str(st.number_input('Valor fixo por item (R$)', min_value=0.0, max_value=100000.0, value=0.0, step=1.0, key='mapeiaai_universal_fixed') or 0))
        if not enabled:
            return source
        out = source.copy()
        divisor = Decimal('1') - ((margem + taxa) / Decimal('100'))
        if divisor <= 0:
            st.error('Margem + taxas não pode chegar a 100% ou mais.')
            return source
        calculated: list[str] = []
        for value in out[base_column]:
            base = _parse_decimal(value)
            calculated.append(_format_money(((base or Decimal('0')) + fixo) / divisor))
        out[target_name] = calculated
        st.session_state[UNIVERSAL_PRICE_COLUMN_KEY] = target_name
        st.success(f'Cálculo aplicado na coluna de origem: {target_name}')
        return out


def _render_mapping_step(source: pd.DataFrame, model: pd.DataFrame, signature: str) -> dict[str, str]:
    st.markdown('### 5. Mapeamento manual com faróis')
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
    rows: list[dict[str, str]] = []

    for index, target in enumerate(model.columns):
        target_name = str(target)
        current_value = current.get(target_name, '')
        default_index = source_options.index(current_value) if current_value in source_options else 0
        selected = st.selectbox(
            f'{target_name}',
            source_options,
            index=default_index,
            key=_mapping_widget_key(signature, index, target_name),
        )
        selected_value = '' if selected == EMPTY_OPTION else selected
        edited[target_name] = selected_value
        rows.append({'Farol': _confidence_flag(target_name, selected_value, source), 'Contrato final': target_name, 'Origem usada': selected_value or '(vazio)'})

    st.session_state[UNIVERSAL_MAPPING_KEY] = edited
    with st.expander('Resumo dos faróis do mapeamento', expanded=True):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=260)
    return edited


def _apply_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    out = output.copy().fillna('')
    for column in out.columns:
        if is_title_column(column):
            out[column] = out[column].map(clean_title_to_limit)
        elif is_description_column(column):
            out[column] = out[column].map(lambda value: re.sub(r'\s+', ' ', str(value or '').strip()))
    return out


def _render_preview_and_download(source: pd.DataFrame, model: pd.DataFrame, mapping: dict[str, str]) -> None:
    st.markdown('### 6. Preview final')
    contract = build_universal_contract(model)
    if source.empty:
        output = empty_universal_output(model, rows=0)
    else:
        output = build_universal_output(source, model, mapping)
    output = _apply_text_rules(output)
    errors = validate_universal_output(output, contract)
    st.session_state[UNIVERSAL_OUTPUT_KEY] = output

    if errors:
        for error in errors:
            st.error(error)
        return

    st.success('Planilha final fiel ao contrato anexado: mesmas colunas, mesma ordem, sem extras.')
    st.dataframe(output.head(80).astype(str), use_container_width=True, height=360)
    st.caption(f'Preview: {len(output)} linha(s) × {len(output.columns)} coluna(s).')

    st.markdown('### 7. Planilha final')
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
    source = _render_source_step(model)
    if not isinstance(source, pd.DataFrame):
        return
    source_with_price = _render_price_calculator(source)
    signature = _reset_universal_state_if_changed(model, source_with_price)
    _render_ai_tools(source_with_price, model)
    mapping = _render_mapping_step(source_with_price, model, signature)
    _render_preview_and_download(source_with_price, model, mapping)


__all__ = ['render_universal_flow']
