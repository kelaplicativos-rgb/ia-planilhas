from __future__ import annotations

import hashlib
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_mapping_bridge import build_and_sync_mapping
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import DEFAULT_CATEGORY_CATALOG, apply_category_suggestions, classify_dataframe
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_template_exporter import template_contract_columns
from bling_app_zero.core.modelo_compactado_universal import resolver_modelo
from bling_app_zero.features_runtime.router import active_contract
from bling_app_zero.ui.flow_context import CONTEXT_UNIVERSAL, activate_csv_finish_mode, set_entry_context
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.mapping_auto_decision import render_mapping_auto_decision_toggle
from bling_app_zero.ui.shared_calculator import render_shared_calculator
from bling_app_zero.ui.shared_final_csv import render_shared_final_csv
from bling_app_zero.ui.shared_mapping import clear_shared_mapping_widgets, render_shared_contract_mapping, suggest_shared_mapping
from bling_app_zero.ui.shared_rules_resources import render_rules_resources_panel
from bling_app_zero.ui.success_banner import render_congratulations_success

UNIVERSAL_MODEL_KEY = 'mapeiaai_universal_model_df'
UNIVERSAL_SOURCE_KEY = 'mapeiaai_universal_source_df'
UNIVERSAL_PROCESSED_KEY = 'mapeiaai_universal_processed_df'
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
UNIVERSAL_SIGNATURE_KEY = 'mapeiaai_universal_signature'
UNIVERSAL_ENGINE_KEY = 'mapeiaai_universal_mapping_engine'
UNIVERSAL_MODEL_FILE_NAME_KEY = 'mapeiaai_universal_model_file_name'
UNIVERSAL_MODEL_FILE_BYTES_KEY = 'mapeiaai_universal_model_file_bytes'
UNIVERSAL_API_SEND_KEY = 'mapeiaai_universal_allow_api_send'
UNIVERSAL_STEP_KEY = 'mapeiaai_universal_current_step'
UNIVERSAL_MAPPING_CONFIRMED_KEY = 'mapeiaai_universal_mapping_confirmed'
UNIVERSAL_PRICE_ENABLED_KEY = 'mapeiaai_universal_price_enabled'
UNIVERSAL_CATEGORY_ENABLED_KEY = 'mapeiaai_universal_category_enabled'
UNIVERSAL_RULES_ENABLED_KEY = 'mapeiaai_universal_rules_enabled'
UNIVERSAL_RULES_CONFIG_KEY = 'mapeiaai_universal_rules_config'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'
SOURCE_MODE_UPLOAD = 'Anexar arquivo de origem'
SOURCE_MODE_SITE = 'Buscar produtos por site'
SOURCE_MODE_KEY = 'mapeiaai_universal_source_mode'
STEP_MODEL = 'modelo'
STEP_SOURCE = 'origem'
STEP_OPTIONS = 'opcionais'
STEP_MAPPING = 'mapeamento'
STEP_BUILD = 'montar'
STEP_DONE = 'final'
STEP_ORDER = (STEP_MODEL, STEP_SOURCE, STEP_OPTIONS, STEP_MAPPING, STEP_BUILD, STEP_DONE)
STEP_LABELS = {
    STEP_MODEL: '1. Modelo',
    STEP_SOURCE: '2. Origem',
    STEP_OPTIONS: '3. Opcionais',
    STEP_MAPPING: '4. Mapeamento',
    STEP_BUILD: '5. Montar planilha',
    STEP_DONE: '6. Final',
}
NO_API_KEYS = (
    'home_bling_connected_same_flow_api_send', 'bling_connected_api_flow_active', 'direct_bling_api_contract_active',
    'direct_bling_operation_applied', 'direct_bling_api_contract_df', 'bling_api_operation', 'api_operation',
    'home_bling_api_operation_choice', 'bling_connected_api_operation', 'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api', 'flow_spine_api_batch_operation', 'source_first_selected_operation',
    'source_first_operation_user_confirmed', 'source_first_operation_pending_choice', 'bling_api_required_selector',
    'bling_api_final_action', 'bling_api_manual_mapping_required', 'bling_api_must_run_ai_check',
)
TECHNICAL_COLUMNS = {'arquivo', 'status'}
UNIVERSAL_CATEGORY_SEARCH_KEY = 'mapeiaai_universal_category_review_search_v1'
UNIVERSAL_CATEGORY_ACTION_KEY = 'mapeiaai_universal_category_review_action_v1'
UNIVERSAL_CATEGORY_VALUE_KEY = 'mapeiaai_universal_category_review_category_v1'
UNIVERSAL_CATEGORY_ATTENTION_KEY = 'mapeiaai_universal_category_review_attention_v1'
UNIVERSAL_CATEGORY_EDITOR_KEY = 'mapeiaai_universal_category_review_editor_v1'
PRODUCT_COLUMNS = ('Nome', 'Descrição', 'Descricao', 'Produto', 'Título', 'Titulo', 'name', 'produto')
CODE_COLUMNS = ('Código', 'Codigo', 'SKU', 'GTIN', 'EAN', 'ID', 'Id')
CATEGORY_COL = 'Categoria do produto'


def _audit(event: str, **details: object) -> None:
    add_audit_event(event, area='UNIVERSAL', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})


def _universal_api_send_allowed() -> bool:
    flow_kind = str(st.session_state.get('mapeiaai_flow_kind') or st.session_state.get('flow_kind') or '').strip()
    entry_path = str(st.session_state.get('mapeiaai_home_entry_path') or '').strip()
    return bool(
        st.session_state.get(UNIVERSAL_API_SEND_KEY)
        or flow_kind == 'universal_model_mapping_api'
        or entry_path == 'mapear_modelo_com_api'
    )


def _force_plain_context() -> None:
    allow_api_send = _universal_api_send_allowed()
    if not allow_api_send:
        for key in NO_API_KEYS:
            st.session_state.pop(key, None)
    set_entry_context(CONTEXT_UNIVERSAL)
    activate_csv_finish_mode()
    st.session_state['mapeiaai_flow_kind'] = 'universal_model_mapping_api' if allow_api_send else 'universal_model_mapping'
    st.session_state['flow_kind'] = 'universal_model_mapping_api' if allow_api_send else 'universal_model_mapping'
    st.session_state['api_flow_active'] = bool(allow_api_send)
    if allow_api_send:
        st.session_state[UNIVERSAL_API_SEND_KEY] = True
        st.session_state['home_bling_connected_same_flow_api_send'] = True
        st.session_state['bling_connected_api_flow_active'] = True
        st.session_state.pop('mapear_planilha_sem_api_active', None)
        st.session_state['active_feature_mode'] = 'api_bling'
        st.session_state['flow_spine_final_destination'] = 'api_bling'
        st.session_state['flow_spine_primary_action_label'] = 'Enviar planilha tratada ao Bling'
    else:
        st.session_state.pop(UNIVERSAL_API_SEND_KEY, None)
        st.session_state['mapear_planilha_sem_api_active'] = True
        st.session_state['active_feature_mode'] = 'csv'
        st.session_state['flow_spine_final_destination'] = 'download'
        st.session_state['flow_spine_primary_action_label'] = 'Download Modelo Mapeado'
    st.session_state['active_feature_operation'] = 'universal'
    st.session_state['active_feature_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_operation'] = 'universal'


def _contract_ok() -> bool:
    contract = active_contract()
    return contract.key in {'universal_csv', 'universal_mapping_csv', 'universal_mapping'} or (contract.mode == 'csv' and contract.operation == 'universal')


def _name_and_bytes(uploaded_file) -> tuple[str, bytes]:
    name = str(getattr(uploaded_file, 'name', '') or '').strip()
    try:
        data = uploaded_file.getvalue()
    except Exception:
        data = b''
    return name, bytes(data or b'')


def _has_valid_columns(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and bool(len(df.columns))


def _is_status_frame(df: pd.DataFrame | None) -> bool:
    if not _has_valid_columns(df):
        return False
    columns = {str(column or '').strip().casefold() for column in df.columns}
    return TECHNICAL_COLUMNS.issubset(columns)


def _model_contract_from_file(name: str, data: bytes) -> pd.DataFrame:
    resolved = resolver_modelo(name, data)
    columns = template_contract_columns(resolved.nome_planilha, resolved.conteudo)
    columns = [str(column).strip() for column in columns if str(column).strip()]
    return pd.DataFrame(columns=columns) if columns else pd.DataFrame()


def _read_model_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    name, data = _name_and_bytes(uploaded_file)
    if name and data:
        st.session_state[UNIVERSAL_MODEL_FILE_NAME_KEY] = name
        st.session_state[UNIVERSAL_MODEL_FILE_BYTES_KEY] = data
    try:
        df = read_uploaded_file(uploaded_file).fillna('')
    except Exception:
        df = pd.DataFrame()
    if _is_status_frame(df) or not _has_valid_columns(df):
        try:
            df = _model_contract_from_file(name, data)
        except Exception as exc:
            st.error(f'Não consegui ler o modelo: {exc}')
            return None
    if not _has_valid_columns(df):
        st.warning('Modelo recebido, mas sem colunas válidas.')
        return None
    if df.empty:
        st.info('Modelo aceito sem linhas. Vou usar as colunas/layout como estrutura final.')
    return df.fillna('')


def _read_source_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        df = read_uploaded_file(uploaded_file).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler a origem: {exc}')
        return None
    if not _has_valid_columns(df) or _is_status_frame(df):
        st.warning('A origem precisa virar uma tabela com colunas de dados.')
        return None
    if df.empty:
        st.warning('A origem precisa ter linhas de dados.')
        return None
    return df


def _store_df(key: str, df: pd.DataFrame | None) -> None:
    if _has_valid_columns(df):
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
        sample_hash = str(pd.util.hash_pandas_object(df.head(80).fillna('').astype(str), index=True).sum())
    return hashlib.sha256(f'{shape}:{columns}:{sample_hash}'.encode('utf-8')).hexdigest()[:16]


def _rules_signature(config: Mapping[str, Any] | None) -> str:
    if not isinstance(config, Mapping):
        return 'none'
    items = sorted((str(key), str(value)) for key, value in config.items())
    return hashlib.sha256(repr(items).encode('utf-8')).hexdigest()[:16]


def _flow_signature(model: pd.DataFrame, source: pd.DataFrame, ai_enabled: bool, rules_enabled: bool, rules_config: Mapping[str, Any] | None = None) -> str:
    return f'{_df_signature(source)}:{_df_signature(model)}:ai={int(ai_enabled)}:rules={int(rules_enabled)}:rules_cfg={_rules_signature(rules_config)}'


def _clear_after_model() -> None:
    for key in (
        UNIVERSAL_SOURCE_KEY,
        UNIVERSAL_PROCESSED_KEY,
        UNIVERSAL_MAPPING_KEY,
        UNIVERSAL_OUTPUT_KEY,
        UNIVERSAL_SIGNATURE_KEY,
        UNIVERSAL_ENGINE_KEY,
        UNIVERSAL_MAPPING_CONFIRMED_KEY,
        UNIVERSAL_RULES_CONFIG_KEY,
        'df_origem_unificada',
        'df_origem_arquivo',
        'df_origem_site',
        'df_origem_site_como_planilha',
        'df_origem_site_como_planilha_universal',
        'neutral_mapping_state_v1',
        'neutral_mapping_report_v1',
    ):
        st.session_state.pop(key, None)
    clear_shared_mapping_widgets('mapeiaai_universal')


def _clear_after_source() -> None:
    for key in (
        UNIVERSAL_PROCESSED_KEY,
        UNIVERSAL_MAPPING_KEY,
        UNIVERSAL_OUTPUT_KEY,
        UNIVERSAL_SIGNATURE_KEY,
        UNIVERSAL_ENGINE_KEY,
        UNIVERSAL_MAPPING_CONFIRMED_KEY,
        UNIVERSAL_RULES_CONFIG_KEY,
        'neutral_mapping_state_v1',
        'neutral_mapping_report_v1',
    ):
        st.session_state.pop(key, None)
    clear_shared_mapping_widgets('mapeiaai_universal')


def _clear_after_options() -> None:
    for key in (
        UNIVERSAL_MAPPING_KEY,
        UNIVERSAL_OUTPUT_KEY,
        UNIVERSAL_SIGNATURE_KEY,
        UNIVERSAL_ENGINE_KEY,
        UNIVERSAL_MAPPING_CONFIRMED_KEY,
        'neutral_mapping_state_v1',
        'neutral_mapping_report_v1',
    ):
        st.session_state.pop(key, None)
    clear_shared_mapping_widgets('mapeiaai_universal')


def _reset_if_changed(model: pd.DataFrame, source: pd.DataFrame, ai_enabled: bool, rules_enabled: bool, rules_config: Mapping[str, Any] | None = None) -> str:
    signature = _flow_signature(model, source, ai_enabled, rules_enabled, rules_config)
    previous = str(st.session_state.get(UNIVERSAL_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        _clear_after_options()
        _audit('universal_flow_state_reset_by_signature_change', previous=previous, current=signature)
    st.session_state[UNIVERSAL_SIGNATURE_KEY] = signature
    return signature


def _set_step(step: str, reason: str) -> None:
    if step not in STEP_ORDER:
        step = STEP_MODEL
    st.session_state[UNIVERSAL_STEP_KEY] = step
    _audit('universal_flow_step_changed', step=step, reason=reason)
    safe_rerun(f'universal_step_{step}_{reason}')


def _infer_step() -> str:
    explicit = str(st.session_state.get(UNIVERSAL_STEP_KEY) or '').strip()
    if explicit in STEP_ORDER:
        return explicit
    if not isinstance(st.session_state.get(UNIVERSAL_MODEL_KEY), pd.DataFrame):
        return STEP_MODEL
    if not isinstance(st.session_state.get(UNIVERSAL_SOURCE_KEY), pd.DataFrame):
        return STEP_SOURCE
    if not isinstance(st.session_state.get(UNIVERSAL_PROCESSED_KEY), pd.DataFrame):
        return STEP_OPTIONS
    if not st.session_state.get(UNIVERSAL_MAPPING_CONFIRMED_KEY):
        return STEP_MAPPING
    if not isinstance(st.session_state.get(UNIVERSAL_OUTPUT_KEY), pd.DataFrame):
        return STEP_BUILD
    return STEP_DONE


def _render_step_bar(current: str) -> None:
    labels = []
    current_idx = STEP_ORDER.index(current) if current in STEP_ORDER else 0
    for idx, step in enumerate(STEP_ORDER):
        marker = '🟢' if idx < current_idx else ('🔵' if idx == current_idx else '⚪')
        labels.append(f'{marker} {STEP_LABELS[step]}')
    st.caption('  →  '.join(labels))


def _render_back_button(current: str) -> None:
    idx = STEP_ORDER.index(current) if current in STEP_ORDER else 0
    if idx <= 0:
        return
    previous = STEP_ORDER[idx - 1]
    if st.button('⬅️ Voltar etapa', key=f'mapeiaai_universal_back_{current}'):
        _set_step(previous, 'back')


def _summary_card(title: str, df: pd.DataFrame | None) -> None:
    if isinstance(df, pd.DataFrame):
        st.caption(f'{title}: {len(df)} linha(s) x {len(df.columns)} coluna(s).')


def _render_model_step() -> pd.DataFrame | None:
    st.markdown('### 1. Anexar Modelo / Mapear')
    model = _current_df(UNIVERSAL_MODEL_KEY)
    uploaded = None
    if not isinstance(model, pd.DataFrame):
        st.caption('Anexe primeiro a planilha modelo exatamente no formato que você quer receber no final.')
        uploaded = st.file_uploader('Planilha modelo final', type=None, key='mapeiaai_universal_model_upload')
        df = _read_model_upload(uploaded)
        if isinstance(df, pd.DataFrame):
            current_sig = _df_signature(_current_df(UNIVERSAL_MODEL_KEY))
            new_sig = _df_signature(df)
            if current_sig != 'none' and current_sig != new_sig:
                _clear_after_model()
            _store_df(UNIVERSAL_MODEL_KEY, df)
            st.session_state['home_modelo_universal_df'] = df.copy().fillna('')
            st.session_state['df_modelo_universal'] = df.copy().fillna('')
            st.session_state['modelo_universal_df'] = df.copy().fillna('')
            _audit('mapear_planilha_modelo_anexado_primeiro', rows=int(len(df)), columns=int(len(df.columns)), original_file_name=str(getattr(uploaded, 'name', '') or ''))
        model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.info('Envie a planilha modelo final para liberar a próxima etapa.')
        return None
    st.success('Modelo final carregado. A saída seguirá exatamente essas colunas e essa ordem.')
    st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
    st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
    if st.button('Continuar para origem dos dados ➡️', use_container_width=True, key='mapeiaai_universal_go_source'):
        _set_step(STEP_SOURCE, 'model_confirmed')
    return model


def _sync_universal_model_for_site_engine(model: pd.DataFrame | None) -> None:
    if isinstance(model, pd.DataFrame) and len(model.columns):
        clean = model.copy().fillna('')
        st.session_state['home_modelo_universal_df'] = clean
        st.session_state['df_modelo_universal'] = clean
        st.session_state['modelo_universal_df'] = clean
    st.session_state['operation_site'] = 'universal'
    st.session_state['tipo_operacao_site'] = 'universal'
    st.session_state['site_capture_operation'] = 'universal'
    st.session_state['home_slim_flow_operation'] = 'universal'
    st.session_state['operacao_final'] = 'universal'
    st.session_state['tipo_operacao_final'] = 'universal'
    st.session_state['origem_final'] = 'site'


def _first_site_df_for_universal() -> pd.DataFrame | None:
    try:
        from bling_app_zero.ui.site_panel_state import get_site_df
        df = get_site_df('universal')
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy().fillna('')
    except Exception:
        pass
    for key in (
        'df_origem_site_como_planilha_universal',
        'df_origem_site_como_planilha',
        'df_site_bruto_universal',
        'df_site_bruto',
        'df_origem_site',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return None


def _store_universal_site_source(df_site: pd.DataFrame) -> pd.DataFrame:
    clean = df_site.copy().fillna('')
    previous = _current_df(UNIVERSAL_SOURCE_KEY)
    if _df_signature(previous) not in {'none', _df_signature(clean)}:
        _clear_after_source()
    _store_df(UNIVERSAL_SOURCE_KEY, clean)
    st.session_state['df_origem_unificada'] = clean.copy().fillna('')
    st.session_state['df_origem_site'] = clean.copy().fillna('')
    st.session_state['df_origem_site_como_planilha'] = clean.copy().fillna('')
    st.session_state['df_origem_site_como_planilha_universal'] = clean.copy().fillna('')
    st.session_state['mapeiaai_universal_source_kind'] = 'site'
    _audit('mapear_planilha_fonte_site_carregada_motor_unico', rows=int(len(clean)), columns=int(len(clean.columns)), source_mode='site', unified_site_engine=True)
    return clean


def _render_source_site(model: pd.DataFrame | None = None) -> pd.DataFrame | None:
    st.caption('A busca por site roda somente nesta tela. A montagem final não será executada aqui.')
    _sync_universal_model_for_site_engine(model)
    try:
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    except Exception as exc:
        st.error(f'Não consegui abrir a origem nova por site: {exc}')
        return _current_df(UNIVERSAL_SOURCE_KEY)

    df_site = _first_site_df_for_universal()
    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        return _store_universal_site_source(df_site)
    return _current_df(UNIVERSAL_SOURCE_KEY)


def _select_source_mode(value: str) -> None:
    st.session_state[SOURCE_MODE_KEY] = value
    st.session_state.pop(UNIVERSAL_SOURCE_KEY, None)
    st.session_state.pop('df_origem_unificada', None)
    st.session_state.pop('df_origem_arquivo', None)
    st.session_state.pop('df_origem_site', None)
    _clear_after_source()


def _render_source_choice_cards() -> str:
    source_mode = str(st.session_state.get(SOURCE_MODE_KEY) or '').strip()
    col_file, col_site = st.columns(2)
    with col_file:
        if st.button('📎 Arquivo', use_container_width=True, key='mapeiaai_universal_source_file_btn'):
            _select_source_mode(SOURCE_MODE_UPLOAD)
            safe_rerun('universal_source_file_selected')
    with col_site:
        if st.button('🌐 Site', use_container_width=True, key='mapeiaai_universal_source_site_btn'):
            _select_source_mode(SOURCE_MODE_SITE)
            safe_rerun('universal_source_site_selected')
    source_mode = str(st.session_state.get(SOURCE_MODE_KEY) or source_mode or '').strip()
    if not source_mode:
        st.warning('Atenção: Escolha Arquivo ou Site.')
    else:
        st.success(f'Origem selecionada: {"Arquivo" if source_mode == SOURCE_MODE_UPLOAD else "Site"}.')
    return source_mode


def _render_source_step(model: pd.DataFrame | None = None) -> pd.DataFrame | None:
    st.markdown('### 2. Origem dos dados')
    st.caption('Nesta tela o sistema apenas carrega a origem. Ele não mapeia e não monta a planilha final.')
    source_mode = _render_source_choice_cards()
    if source_mode == SOURCE_MODE_SITE:
        source = _render_source_site(model)
    elif source_mode == SOURCE_MODE_UPLOAD:
        uploaded = st.file_uploader('Arquivo de origem dos dados', type=None, key='mapeiaai_universal_source_upload')
        source = _read_source_upload(uploaded)
        if isinstance(source, pd.DataFrame):
            previous = _current_df(UNIVERSAL_SOURCE_KEY)
            if _df_signature(previous) not in {'none', _df_signature(source)}:
                _clear_after_source()
            _store_df(UNIVERSAL_SOURCE_KEY, source)
            st.session_state['df_origem_unificada'] = source.copy().fillna('')
            st.session_state['df_origem_arquivo'] = source.copy().fillna('')
            st.session_state['mapeiaai_universal_source_kind'] = 'arquivo'
            _audit('mapear_planilha_fonte_anexada', rows=int(len(source)), columns=int(len(source.columns)), source_mode='upload')
        source = _current_df(UNIVERSAL_SOURCE_KEY)
    else:
        return None
    if not isinstance(source, pd.DataFrame):
        st.info('Carregue a origem de dados para liberar a próxima etapa.')
        return None
    st.success(f'Origem carregada: {len(source)} linha(s) x {len(source.columns)} coluna(s).')
    with st.expander('Ver origem carregada', expanded=False):
        st.dataframe(source.head(30).astype(str), use_container_width=True, height=280)
    if st.button('Continuar para opcionais ➡️', use_container_width=True, key='mapeiaai_universal_go_options'):
        _set_step(STEP_OPTIONS, 'source_confirmed')
    return source


def _render_price_group(source: pd.DataFrame, model: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    st.markdown('### Preço')
    enabled = st.toggle('Preço / cálculo marketplace', value=bool(st.session_state.get(UNIVERSAL_PRICE_ENABLED_KEY)), key='mapeiaai_universal_toggle_price')
    st.session_state[UNIVERSAL_PRICE_ENABLED_KEY] = bool(enabled)
    if not enabled:
        st.caption('Desligado. O mapeamento usará os preços originais da origem, se existirem.')
        _audit('mapear_planilha_grupo_preco_toggle', enabled=False, grouped_toggle=True)
        return source, False
    _audit('mapear_planilha_grupo_preco_toggle', enabled=True, grouped_toggle=True)
    return render_shared_calculator(source, model=model, key_prefix='mapeiaai_universal', force_enabled=True), True


def _render_category_config() -> tuple[bool, float]:
    st.markdown('### Categorização')
    enabled = st.toggle('Categorização inteligente', value=bool(st.session_state.get(UNIVERSAL_CATEGORY_ENABLED_KEY)), key='mapeiaai_universal_toggle_category')
    st.session_state[UNIVERSAL_CATEGORY_ENABLED_KEY] = bool(enabled)
    if not enabled:
        st.caption('Desligado. As categorias serão mantidas como vieram da origem/mapeamento.')
        return False, 0.80
    confidence = st.slider('Confiança mínima para sugerir/aplicar categoria', 0.50, 0.99, 0.80, 0.01, key='mapeiaai_universal_category_confidence_min')
    st.caption('Confira as categorias abaixo. Edite “Categoria corrigida” antes de avançar para o mapeamento.')
    return True, float(confidence)


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    return ''


def _row_text(row: pd.Series, columns: tuple[str, ...]) -> str:
    values: list[str] = []
    for column in columns:
        if column in row.index:
            value = str(row.get(column) or '').strip()
            if value:
                values.append(value)
    return ' · '.join(values)


def _build_category_review_preview(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    category_col = CATEGORY_COL if CATEGORY_COL in df.columns else None
    product_col = _first_existing_column(df, PRODUCT_COLUMNS)
    code_col = _first_existing_column(df, CODE_COLUMNS)
    rows: list[dict[str, object]] = []
    for position, (_idx, row) in enumerate(df.fillna('').iterrows()):
        current = str(row.get('categoria_atual_ia') or (row.get(category_col) if category_col else '') or '').strip()
        suggested = str(row.get('categoria_sugerida_ia') or (row.get(category_col) if category_col else '') or '').strip()
        action = str(row.get('acao_categoria_ia') or 'MANTER').strip() or 'MANTER'
        final_category = suggested or current
        rows.append(
            {
                '__row_index': int(position),
                'linha': int(position) + 1,
                'Produto': str(row.get(product_col) or _row_text(row, PRODUCT_COLUMNS) or '').strip(),
                'Código/SKU': str(row.get(code_col) or _row_text(row, CODE_COLUMNS) or '').strip(),
                'Categoria atual': current,
                'Categoria sugerida': suggested,
                'Categoria corrigida': final_category,
                'Ação': action,
                'Confiança': row.get('confianca_categoria_ia', ''),
                'Motivo': str(row.get('motivo_categoria_ia') or '').strip(),
            }
        )
    return pd.DataFrame(rows)


def _filter_category_review(preview: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(preview, pd.DataFrame) or preview.empty:
        return preview
    with st.container(border=True):
        st.markdown('**Preview de produtos e categorias**')
        left, middle, right = st.columns([2, 1, 1])
        search = left.text_input('Filtrar por produto, código ou categoria', key=UNIVERSAL_CATEGORY_SEARCH_KEY, placeholder='Ex.: power bank, cabo, fonte, adaptador...')
        actions = ['Todas'] + sorted({str(v) for v in preview['Ação'].fillna('').astype(str) if str(v).strip()})
        action = middle.selectbox('Ação', actions, key=UNIVERSAL_CATEGORY_ACTION_KEY)
        categories = sorted({str(v).strip() for v in preview['Categoria corrigida'].fillna('').astype(str) if str(v).strip()})
        category = right.selectbox('Categoria', ['Todas'] + categories, key=UNIVERSAL_CATEGORY_VALUE_KEY)
        attention_only = st.checkbox('Mostrar somente corrigidos/revisar', value=False, key=UNIVERSAL_CATEGORY_ATTENTION_KEY)

    filtered = preview.copy().fillna('')
    if search.strip():
        token = search.strip().casefold()
        haystack = filtered.drop(columns=['__row_index'], errors='ignore').astype(str).agg(' '.join, axis=1).str.casefold()
        filtered = filtered[haystack.str.contains(token, regex=False, na=False)]
    if action != 'Todas':
        filtered = filtered[filtered['Ação'].astype(str) == action]
    if category != 'Todas':
        filtered = filtered[filtered['Categoria corrigida'].astype(str) == category]
    if attention_only:
        filtered = filtered[filtered['Ação'].astype(str).ne('MANTER')]
    return filtered


def _category_options(preview: pd.DataFrame) -> list[str]:
    options = list(DEFAULT_CATEGORY_CATALOG)
    if isinstance(preview, pd.DataFrame) and not preview.empty:
        for column in ('Categoria atual', 'Categoria sugerida', 'Categoria corrigida'):
            if column in preview.columns:
                options.extend([str(v).strip() for v in preview[column].fillna('').astype(str) if str(v).strip()])
    return sorted(dict.fromkeys(options))


def _editor_row_to_base_index(row: pd.Series, max_rows: int) -> int | None:
    candidates: list[tuple[object, bool]] = []
    if '__row_index' in row.index:
        candidates.append((row.get('__row_index'), False))
    if 'linha' in row.index:
        candidates.append((row.get('linha'), True))
    for value, one_based in candidates:
        try:
            if value is None or pd.isna(value):
                continue
        except Exception:
            pass
        try:
            number = int(float(str(value).strip()))
        except Exception:
            continue
        index = number - 1 if one_based else number
        if 0 <= index < max_rows:
            return index
    return None


def _render_universal_category_review(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    preview = _build_category_review_preview(df)
    if preview.empty:
        return df
    filtered = _filter_category_review(preview)
    st.caption(f'Mostrando {len(filtered)} de {len(preview)} produto(s). Edite apenas “Categoria corrigida” antes de avançar.')
    if filtered.empty:
        st.info('Nenhum produto encontrado com estes filtros.')
        return df
    edited = st.data_editor(
        filtered,
        key=UNIVERSAL_CATEGORY_EDITOR_KEY,
        use_container_width=True,
        hide_index=True,
        height=430,
        disabled=[col for col in filtered.columns if col != 'Categoria corrigida'],
        column_order=['linha', 'Produto', 'Código/SKU', 'Categoria atual', 'Categoria sugerida', 'Categoria corrigida', 'Ação', 'Confiança', 'Motivo'],
        column_config={
            'Categoria corrigida': st.column_config.SelectboxColumn('Categoria corrigida', options=_category_options(preview), required=True),
            'linha': st.column_config.NumberColumn('Linha', disabled=True),
            'Produto': st.column_config.TextColumn('Produto', disabled=True),
            'Código/SKU': st.column_config.TextColumn('Código/SKU', disabled=True),
            'Categoria atual': st.column_config.TextColumn('Categoria atual', disabled=True),
            'Categoria sugerida': st.column_config.TextColumn('Categoria sugerida', disabled=True),
            'Ação': st.column_config.TextColumn('Ação', disabled=True),
            'Confiança': st.column_config.TextColumn('Confiança', disabled=True),
            'Motivo': st.column_config.TextColumn('Motivo', disabled=True),
        },
    )
    output = df.copy().fillna('')
    if CATEGORY_COL not in output.columns:
        output[CATEGORY_COL] = ''
    manual_changes = 0
    for _, row in edited.iterrows():
        row_index = _editor_row_to_base_index(row, len(output))
        if row_index is None:
            continue
        new_category = str(row.get('Categoria corrigida') or '').strip()
        if not new_category:
            continue
        old_category = str(output.at[output.index[row_index], CATEGORY_COL] or '').strip()
        if new_category != old_category:
            output.at[output.index[row_index], CATEGORY_COL] = new_category
            manual_changes += 1
    if manual_changes:
        st.success(f'{manual_changes} categoria(s) ajustada(s) na prévia. Clique em “Aplicar opcionais e ir para mapeamento” para gravar no fluxo.')
        _audit('universal_category_preview_manual_edits_ready', manual_changes=manual_changes, rows=int(len(output)))
    return output


def _apply_category_group(source: pd.DataFrame, confidence_min: float) -> pd.DataFrame:
    try:
        analyzed, stats = classify_dataframe(source)
        output, applied = apply_category_suggestions(analyzed, confidence_min=float(confidence_min), keep_helper_columns=True)
    except Exception as exc:
        st.warning(f'Categorização não aplicada: {exc}')
        _audit('mapear_planilha_grupo_categoria_toggle', enabled=True, grouped_toggle=True, applied=False, error=str(exc)[:220])
        return source
    st.success(f'Categorização analisada: {stats.get("total", 0)} produto(s), {applied} categoria(s) aplicada(s).')
    reviewed = _render_universal_category_review(output)
    _audit('mapear_planilha_grupo_categoria_toggle', enabled=True, grouped_toggle=True, applied=True, rows=int(len(reviewed)), preview_filter=True, manual_review_enabled=True)
    return reviewed


def _render_rules_group(source: pd.DataFrame, model: pd.DataFrame) -> tuple[Mapping[str, Any] | None, bool]:
    st.markdown('### Regras e recursos')
    enabled = st.toggle('Regras e recursos inteligentes no download', value=bool(st.session_state.get(UNIVERSAL_RULES_ENABLED_KEY)), key='mapeiaai_universal_toggle_rules')
    st.session_state[UNIVERSAL_RULES_ENABLED_KEY] = bool(enabled)
    if not enabled:
        st.caption('Desligado. O download seguirá somente o mapeamento e as colunas finais do modelo.')
        _audit('mapear_planilha_grupo_regras_toggle', enabled=False, grouped_toggle=True)
        return None, False
    _audit('mapear_planilha_grupo_regras_toggle', enabled=True, grouped_toggle=True)
    return render_rules_resources_panel(source, model, enabled=True, key_prefix='mapeiaai_universal'), True


def _render_ai_tools(source: pd.DataFrame, model: pd.DataFrame, enabled: bool) -> None:
    if not enabled:
        return
    if st.button('Regerar sugestão de mapeamento com IA', use_container_width=True, key='mapeiaai_universal_regen_ai_mapping'):
        suggested, engine = suggest_shared_mapping(source, model, operation='universal')
        st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
        st.session_state[UNIVERSAL_ENGINE_KEY] = engine
        st.session_state.pop(UNIVERSAL_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(UNIVERSAL_OUTPUT_KEY, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
        st.success('Sugestões de mapeamento atualizadas.')
        safe_rerun('universal_ai_mapping_regenerated')


def _render_mapping_ai_toggle() -> bool:
    st.markdown('### 4. Mapeamento')
    mapping_ai = render_mapping_auto_decision_toggle(
        widget_key='mapeiaai_universal_toggle_mapping_auto',
        source='universal_flow',
        default=False,
        label='Mapeamento automático com IA',
    )
    st.session_state['mapeiaai_universal_toggle_mapping_ai'] = bool(mapping_ai)
    _audit('mapear_planilha_grupo_mapeamento_toggle', enabled=bool(mapping_ai), grouped_toggle=True)
    return bool(mapping_ai)


def _render_bling_destination_notice() -> None:
    st.markdown('### Destino final')
    if _universal_api_send_allowed():
        st.success('Fluxo Universal com Bling conectado: depois do preview, você pode baixar a planilha ou enviar por API quando a operação real for identificada.')
        _audit('mapear_planilha_bling_destination_notice_rendered', requires_restart_for_api=False, final_destination='api_bling')
        return
    st.info('Este caminho finaliza em download. Para enviar ao Bling, conecte ao Bling antes de entrar no fluxo Universal ou use o caminho “Bling conectado”.')
    _audit('mapear_planilha_bling_destination_notice_rendered', requires_restart_for_api=True, final_destination='download')


def _render_options_step(model: pd.DataFrame, source: pd.DataFrame) -> None:
    st.markdown('### 3. Opcionais')
    st.caption('Esta tela aplica opcionais e permite conferir/corrigir categorias antes do mapeamento.')
    processed = source.copy().fillna('')
    processed, price_enabled = _render_price_group(processed, model)
    category_enabled, category_confidence = _render_category_config()
    if category_enabled:
        processed = _apply_category_group(processed, category_confidence)
    rules_config, rules_enabled = _render_rules_group(processed, model)
    if st.button('Aplicar opcionais e ir para mapeamento ➡️', use_container_width=True, key='mapeiaai_universal_apply_options'):
        _store_df(UNIVERSAL_PROCESSED_KEY, processed)
        st.session_state[UNIVERSAL_PRICE_ENABLED_KEY] = bool(price_enabled)
        st.session_state[UNIVERSAL_CATEGORY_ENABLED_KEY] = bool(category_enabled)
        st.session_state[UNIVERSAL_RULES_ENABLED_KEY] = bool(rules_enabled)
        st.session_state[UNIVERSAL_RULES_CONFIG_KEY] = dict(rules_config or {})
        _clear_after_options()
        _audit('universal_options_applied_before_mapping', rows=int(len(processed)), columns=int(len(processed.columns)), price_enabled=price_enabled, category_enabled=category_enabled, rules_enabled=rules_enabled, category_preview_reviewed=category_enabled)
        _set_step(STEP_MAPPING, 'options_applied')


def _render_mapping_step(model: pd.DataFrame, processed: pd.DataFrame) -> None:
    st.caption('Nesta tela o sistema só mapeia colunas. Ele ainda NÃO monta a planilha final.')
    mapping_ai = _render_mapping_ai_toggle()
    rules_enabled = bool(st.session_state.get(UNIVERSAL_RULES_ENABLED_KEY))
    rules_config = st.session_state.get(UNIVERSAL_RULES_CONFIG_KEY)
    signature = _reset_if_changed(model, processed, mapping_ai, rules_enabled, rules_config if isinstance(rules_config, Mapping) else None)
    if mapping_ai and str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or '') == 'manual_sem_ia':
        st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)
        st.session_state.pop(UNIVERSAL_ENGINE_KEY, None)
        st.session_state.pop(UNIVERSAL_MAPPING_CONFIRMED_KEY, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
    _render_ai_tools(processed, model, mapping_ai)
    mapping = render_shared_contract_mapping(
        processed,
        model,
        signature=signature,
        mapping_state_key=UNIVERSAL_MAPPING_KEY,
        engine_state_key=UNIVERSAL_ENGINE_KEY,
        key_prefix='mapeiaai_universal',
        ai_enabled=mapping_ai,
    )
    mapping, _mapping_rows = build_and_sync_mapping(
        processed,
        model,
        mapping,
        operation='universal',
        signature=signature,
        engine=str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or 'local'),
        mapping_state_key=UNIVERSAL_MAPPING_KEY,
        engine_state_key=UNIVERSAL_ENGINE_KEY,
    )
    st.session_state[UNIVERSAL_MAPPING_KEY] = dict(mapping or {})
    st.info('Quando o mapeamento estiver correto, avance. A planilha final só será montada na próxima tela.')
    if st.button('Confirmar mapeamento e ir para montagem ➡️', use_container_width=True, key='mapeiaai_universal_confirm_mapping'):
        st.session_state[UNIVERSAL_MAPPING_CONFIRMED_KEY] = True
        st.session_state.pop(UNIVERSAL_OUTPUT_KEY, None)
        _audit('universal_mapping_confirmed_without_building_output', mapped_fields=len(dict(mapping or {})), one_step_per_screen=True)
        _set_step(STEP_BUILD, 'mapping_confirmed')


def _render_build_step(model: pd.DataFrame, processed: pd.DataFrame) -> None:
    st.markdown('### 5. Montar planilha final')
    st.caption('Agora sim o sistema executa o processamento pesado: aplicar mapeamento, regras finais, preview, download e destino Bling quando habilitado.')
    mapping = st.session_state.get(UNIVERSAL_MAPPING_KEY)
    if not isinstance(mapping, dict) or not mapping:
        st.warning('Confirme o mapeamento antes de montar a planilha final.')
        if st.button('Voltar ao mapeamento', key='mapeiaai_universal_back_to_mapping_missing'):
            _set_step(STEP_MAPPING, 'missing_mapping')
        return
    rules_config = st.session_state.get(UNIVERSAL_RULES_CONFIG_KEY)
    rules_enabled = bool(st.session_state.get(UNIVERSAL_RULES_ENABLED_KEY))
    run_now = st.button('✅ Montar planilha final agora', use_container_width=True, key='mapeiaai_universal_build_final_now')
    output_ready = isinstance(st.session_state.get(UNIVERSAL_OUTPUT_KEY), pd.DataFrame)
    if not run_now and not output_ready:
        st.info('A planilha ainda não foi montada. Clique no botão acima para processar somente nesta etapa.')
        return
    output = render_shared_final_csv(
        processed,
        model,
        mapping,
        key_prefix='mapeiaai_universal',
        file_name='mapeiaai_planilha_final_mapeada.csv',
        run_smart_features=rules_enabled,
        smart_rules_config=rules_config if isinstance(rules_config, Mapping) else None,
    )
    if isinstance(output, pd.DataFrame):
        st.session_state[UNIVERSAL_OUTPUT_KEY] = output
        render_congratulations_success(area='UNIVERSAL', context='download_final_planilha_mapeada')
        _render_bling_destination_notice()
        _audit(
            'mapear_planilha_preview_download_pronto',
            rows=int(len(output)),
            columns=int(len(output.columns)),
            csv=True,
            unified_origin=True,
            price_enabled=bool(st.session_state.get(UNIVERSAL_PRICE_ENABLED_KEY)),
            category_enabled=bool(st.session_state.get(UNIVERSAL_CATEGORY_ENABLED_KEY)),
            rules_enabled=rules_enabled,
            api_send_allowed=_universal_api_send_allowed(),
            one_step_per_screen=True,
        )


def render_universal_flow() -> None:
    _force_plain_context()
    if not _contract_ok():
        st.warning('Este fluxo é exclusivo para Mapear planilha por contrato / Universal CSV.')
        return
    st.markdown('## Anexar Modelo / Mapear Planilha')
    if _universal_api_send_allowed():
        st.caption('Bling conectado: o fluxo agora roda uma etapa por tela para evitar Running... em cada ação.')
    else:
        st.caption('Sem API: uma etapa por tela. A planilha final só é montada depois do mapeamento confirmado.')

    current_step = _infer_step()
    st.session_state[UNIVERSAL_STEP_KEY] = current_step
    _render_step_bar(current_step)
    _render_back_button(current_step)

    model = _current_df(UNIVERSAL_MODEL_KEY)
    source = _current_df(UNIVERSAL_SOURCE_KEY)
    processed = _current_df(UNIVERSAL_PROCESSED_KEY)
    _summary_card('Modelo', model)
    _summary_card('Origem', source)
    _summary_card('Dados preparados', processed)

    if current_step == STEP_MODEL:
        _render_model_step()
        return

    if not isinstance(model, pd.DataFrame):
        st.warning('Anexe o modelo antes de continuar.')
        _set_step(STEP_MODEL, 'missing_model')
        return

    if current_step == STEP_SOURCE:
        _render_source_step(model)
        return

    if not isinstance(source, pd.DataFrame):
        st.warning('Carregue a origem antes de continuar.')
        _set_step(STEP_SOURCE, 'missing_source')
        return

    if current_step == STEP_OPTIONS:
        _render_options_step(model, source)
        return

    if not isinstance(processed, pd.DataFrame):
        _store_df(UNIVERSAL_PROCESSED_KEY, source)
        processed = source.copy().fillna('')

    if current_step == STEP_MAPPING:
        _render_mapping_step(model, processed)
        return

    if current_step == STEP_BUILD:
        _render_build_step(model, processed)
        return

    if current_step == STEP_DONE:
        _render_build_step(model, processed)
        return


__all__ = ['render_universal_flow']
