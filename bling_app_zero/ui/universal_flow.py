from __future__ import annotations

import hashlib
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_mapping_bridge import build_and_sync_mapping
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import apply_category_suggestions, classify_dataframe
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
UNIVERSAL_MAPPING_KEY = 'mapeiaai_universal_mapping'
UNIVERSAL_OUTPUT_KEY = 'mapeiaai_universal_output_df'
UNIVERSAL_SIGNATURE_KEY = 'mapeiaai_universal_signature'
UNIVERSAL_ENGINE_KEY = 'mapeiaai_universal_mapping_engine'
UNIVERSAL_MODEL_FILE_NAME_KEY = 'mapeiaai_universal_model_file_name'
UNIVERSAL_MODEL_FILE_BYTES_KEY = 'mapeiaai_universal_model_file_bytes'
RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_flow.py'
SOURCE_MODE_UPLOAD = 'Anexar arquivo de origem'
SOURCE_MODE_SITE = 'Buscar produtos por site'
NO_API_KEYS = (
    'home_bling_connected_same_flow_api_send', 'bling_connected_api_flow_active', 'direct_bling_api_contract_active',
    'direct_bling_operation_applied', 'direct_bling_api_contract_df', 'bling_api_operation', 'api_operation',
    'home_bling_api_operation_choice', 'bling_connected_api_operation', 'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api', 'flow_spine_api_batch_operation', 'source_first_selected_operation',
    'source_first_operation_user_confirmed', 'source_first_operation_pending_choice', 'bling_api_required_selector',
    'bling_api_final_action', 'bling_api_manual_mapping_required', 'bling_api_must_run_ai_check',
)
TECHNICAL_COLUMNS = {'arquivo', 'status'}


def _audit(event: str, **details: object) -> None:
    add_audit_event(event, area='UNIVERSAL', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})


def _force_plain_context() -> None:
    for key in NO_API_KEYS:
        st.session_state.pop(key, None)
    set_entry_context(CONTEXT_UNIVERSAL)
    activate_csv_finish_mode()
    st.session_state['mapeiaai_flow_kind'] = 'universal_model_mapping'
    st.session_state['flow_kind'] = 'universal_model_mapping'
    st.session_state['api_flow_active'] = False
    st.session_state['mapear_planilha_sem_api_active'] = True
    st.session_state['active_feature_mode'] = 'csv'
    st.session_state['active_feature_operation'] = 'universal'
    st.session_state['active_feature_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_operation'] = 'universal'
    st.session_state['flow_spine_final_destination'] = 'download'
    st.session_state['flow_spine_primary_action_label'] = 'Download Modelo Mapeado'


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


def _reset_if_changed(model: pd.DataFrame, source: pd.DataFrame, ai_enabled: bool, rules_enabled: bool, rules_config: Mapping[str, Any] | None = None) -> str:
    signature = _flow_signature(model, source, ai_enabled, rules_enabled, rules_config)
    previous = str(st.session_state.get(UNIVERSAL_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        for key in (UNIVERSAL_MAPPING_KEY, UNIVERSAL_OUTPUT_KEY, UNIVERSAL_ENGINE_KEY, 'neutral_mapping_state_v1', 'neutral_mapping_report_v1'):
            st.session_state.pop(key, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
        _audit('universal_flow_state_reset_by_signature_change', previous=previous, current=signature)
    st.session_state[UNIVERSAL_SIGNATURE_KEY] = signature
    return signature


def _render_model_step() -> pd.DataFrame | None:
    st.markdown('### 1. Anexar Modelo / Mapear')
    model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.caption('Anexe primeiro a planilha modelo exatamente no formato que você quer receber no final.')
        uploaded = st.file_uploader('Planilha modelo final', type=None, key='mapeiaai_universal_model_upload')
        df = _read_model_upload(uploaded)
        if isinstance(df, pd.DataFrame):
            _store_df(UNIVERSAL_MODEL_KEY, df)
            st.session_state['home_modelo_universal_df'] = df.copy().fillna('')
            st.session_state['df_modelo_universal'] = df.copy().fillna('')
            st.session_state['modelo_universal_df'] = df.copy().fillna('')
            _audit('mapear_planilha_modelo_anexado_primeiro', rows=int(len(df)), columns=int(len(df.columns)), original_file_name=str(getattr(uploaded, 'name', '') or ''))
        model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.info('Envie a planilha modelo final para liberar a origem de dados, os opcionais, o mapeamento, o preview e o download.')
        return None
    st.success('Modelo final carregado. A saída seguirá exatamente essas colunas e essa ordem.')
    st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
    st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
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
    _store_df(UNIVERSAL_SOURCE_KEY, clean)
    st.session_state['df_origem_unificada'] = clean.copy().fillna('')
    st.session_state['df_origem_site'] = clean.copy().fillna('')
    st.session_state['df_origem_site_como_planilha'] = clean.copy().fillna('')
    st.session_state['df_origem_site_como_planilha_universal'] = clean.copy().fillna('')
    st.session_state['mapeiaai_universal_source_kind'] = 'site'
    _audit('mapear_planilha_fonte_site_carregada_motor_unico', rows=int(len(clean)), columns=int(len(clean.columns)), source_mode='site', unified_site_engine=True)
    return clean


def _render_source_site(model: pd.DataFrame | None = None) -> pd.DataFrame | None:
    st.caption('A busca por site usa a mesma origem nova do Bling conectado. O que muda é só o destino final: download ou envio ao Bling.')
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


def _render_source_step(model: pd.DataFrame | None = None) -> pd.DataFrame | None:
    st.markdown('### 2. Origem de dados')
    st.caption('Agora escolha de onde virão os dados que serão inseridos no modelo anexado.')
    source_mode = st.radio('Como quer trazer os dados da origem?', [SOURCE_MODE_UPLOAD, SOURCE_MODE_SITE], key='mapeiaai_universal_source_mode')
    if source_mode == SOURCE_MODE_SITE:
        source = _render_source_site(model)
    else:
        uploaded = st.file_uploader('Arquivo de origem dos dados', type=None, key='mapeiaai_universal_source_upload')
        source = _read_source_upload(uploaded)
        if isinstance(source, pd.DataFrame):
            _store_df(UNIVERSAL_SOURCE_KEY, source)
            st.session_state['df_origem_unificada'] = source.copy().fillna('')
            st.session_state['df_origem_arquivo'] = source.copy().fillna('')
            st.session_state['mapeiaai_universal_source_kind'] = 'arquivo'
            _audit('mapear_planilha_fonte_anexada', rows=int(len(source)), columns=int(len(source.columns)), source_mode='upload')
        source = _current_df(UNIVERSAL_SOURCE_KEY)
    if not isinstance(source, pd.DataFrame):
        st.info('Carregue a origem de dados para liberar os opcionais, o mapeamento, o preview e o download.')
        return None
    st.success(f'Origem carregada: {len(source)} linha(s) x {len(source.columns)} coluna(s).')
    with st.expander('Ver origem carregada', expanded=False):
        st.dataframe(source.head(30).astype(str), use_container_width=True, height=280)
    return source


def _render_toggles() -> dict[str, bool]:
    st.markdown('### 3. Toggles e opcionais')
    col1, col2 = st.columns(2)
    with col1:
        price = st.toggle('Preço / cálculo marketplace', value=False, key='mapeiaai_universal_toggle_price')
        category = st.toggle('Categorização inteligente', value=False, key='mapeiaai_universal_toggle_category')
    with col2:
        rules = st.toggle('Regras e recursos inteligentes no download', value=False, key='mapeiaai_universal_toggle_rules')
    toggles = {'price': bool(price), 'category': bool(category), 'rules': bool(rules)}
    _audit('mapear_planilha_toggles_definidos', **toggles, mapping_auto_rendered_in_mapping_section=True)
    return toggles


def _apply_category(source: pd.DataFrame, enabled: bool) -> pd.DataFrame:
    if not enabled:
        return source
    st.markdown('### Categorização inteligente')
    try:
        analyzed, stats = classify_dataframe(source)
        confidence = st.slider('Confiança mínima para aplicar categoria', 0.50, 0.99, 0.80, 0.01, key='mapeiaai_universal_category_confidence_min')
        output, applied = apply_category_suggestions(analyzed, confidence_min=float(confidence), keep_helper_columns=True)
    except Exception as exc:
        st.warning(f'Categorização não aplicada: {exc}')
        return source
    st.success(f'Categorização analisada: {stats.get("total", 0)} produto(s), {applied} categoria(s) aplicada(s).')
    return output


def _render_ai_tools(source: pd.DataFrame, model: pd.DataFrame, enabled: bool) -> None:
    if not enabled:
        return
    st.markdown('### Inteligência Artificial')
    if st.button('Regerar sugestão de mapeamento com IA', use_container_width=True, key='mapeiaai_universal_regen_ai_mapping'):
        suggested, engine = suggest_shared_mapping(source, model, operation='universal')
        st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
        st.session_state[UNIVERSAL_ENGINE_KEY] = engine
        clear_shared_mapping_widgets('mapeiaai_universal')
        st.success('Sugestões de mapeamento atualizadas.')
        safe_rerun('universal_ai_mapping_regenerated')


def _render_mapping_ai_toggle() -> bool:
    st.markdown('### Mapeamento')
    mapping_ai = render_mapping_auto_decision_toggle(
        widget_key='mapeiaai_universal_toggle_mapping_auto',
        source='universal_flow',
        default=False,
        label='Mapeamento automático com IA',
    )
    st.session_state['mapeiaai_universal_toggle_mapping_ai'] = bool(mapping_ai)
    return bool(mapping_ai)


def _render_bling_destination_notice() -> None:
    st.markdown('### Destino final')
    st.info('Este caminho finaliza em download. Para enviar ao Bling, inicie uma nova operação pelo botão “Bling conectado” e use a mesma Origem dos dados nova.')
    st.warning('Se não houver conexão com o Bling, será necessário voltar ao início, conectar ao Bling e refazer/retomar a operação em modo API para liberar o envio final.')
    _audit('mapear_planilha_bling_destination_notice_rendered', requires_restart_for_api=True, final_destination='download')


def render_universal_flow() -> None:
    _force_plain_context()
    if not _contract_ok():
        st.warning('Este fluxo é exclusivo para Mapear planilha por contrato / Universal CSV.')
        return
    st.markdown('## Anexar Modelo / Mapear Planilha')
    st.caption('Sem API: anexe o modelo final, escolha a origem dos dados, use opcionais, revise o mapeamento, veja o preview e baixe a planilha idêntica.')
    model = _render_model_step()
    if not isinstance(model, pd.DataFrame):
        return
    source = _render_source_step(model)
    if not isinstance(source, pd.DataFrame):
        return
    toggles = _render_toggles()
    processed = source.copy().fillna('')
    if toggles['price']:
        processed = render_shared_calculator(processed, model=model, key_prefix='mapeiaai_universal', force_enabled=True)
    processed = _apply_category(processed, toggles['category'])
    rules_config = render_rules_resources_panel(processed, model, enabled=toggles['rules'], key_prefix='mapeiaai_universal')
    mapping_ai = _render_mapping_ai_toggle()
    signature = _reset_if_changed(model, processed, mapping_ai, toggles['rules'], rules_config)
    if mapping_ai and str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or '') == 'manual_sem_ia':
        st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)
        st.session_state.pop(UNIVERSAL_ENGINE_KEY, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
    _render_ai_tools(processed, model, mapping_ai)
    mapping = render_shared_contract_mapping(processed, model, signature=signature, mapping_state_key=UNIVERSAL_MAPPING_KEY, engine_state_key=UNIVERSAL_ENGINE_KEY, key_prefix='mapeiaai_universal', ai_enabled=mapping_ai)
    mapping, _mapping_rows = build_and_sync_mapping(processed, model, mapping, operation='universal', signature=signature, engine=str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or 'local'), mapping_state_key=UNIVERSAL_MAPPING_KEY, engine_state_key=UNIVERSAL_ENGINE_KEY)
    output = render_shared_final_csv(processed, model, mapping, key_prefix='mapeiaai_universal', file_name='mapeiaai_planilha_final_mapeada.csv', run_smart_features=toggles['rules'], smart_rules_config=rules_config)
    if isinstance(output, pd.DataFrame):
        st.session_state[UNIVERSAL_OUTPUT_KEY] = output
        render_congratulations_success(area='UNIVERSAL', context='download_final_planilha_mapeada')
        _render_bling_destination_notice()
        _audit('mapear_planilha_preview_download_pronto', rows=int(len(output)), columns=int(len(output.columns)), csv=True, unified_origin=True)


__all__ = ['render_universal_flow']