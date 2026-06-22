from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_mapping_bridge import build_and_sync_mapping
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import apply_category_suggestions, classify_dataframe
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.features_runtime.router import active_contract
from bling_app_zero.pipelines.site_pipeline import run_pipeline as run_site_pipeline
from bling_app_zero.ui.flow_context import CONTEXT_UNIVERSAL, activate_csv_finish_mode, set_entry_context
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.mapping_auto_decision import render_mapping_auto_decision_toggle
from bling_app_zero.ui.shared_calculator import render_shared_calculator
from bling_app_zero.ui.shared_final_csv import render_shared_final_csv
from bling_app_zero.ui.shared_mapping import clear_shared_mapping_widgets, render_shared_contract_mapping, suggest_shared_mapping
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
MODEL_UPLOAD_LABEL = 'Modelo para download fiel: use XLSX, XLSM ou CSV. Modelos sem linhas, só com cabeçalho/layout, também são aceitos.'
SOURCE_UPLOAD_LABEL = 'Origem de dados: XLSX, XLS, CSV, XLSM, XLSB, XML, HTML, MHTML e PDF. A origem precisa ter linhas de dados.'
LEGACY_UNIVERSAL_MODEL_KEYS = (
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
)
NO_API_KEYS = (
    'home_bling_connected_same_flow_api_send', 'bling_connected_api_flow_active', 'direct_bling_api_contract_active',
    'direct_bling_operation_applied', 'direct_bling_api_contract_df', 'bling_api_operation', 'api_operation',
    'home_bling_api_operation_choice', 'bling_connected_api_operation', 'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api', 'flow_spine_api_batch_operation', 'source_first_selected_operation',
    'source_first_operation_user_confirmed', 'source_first_operation_pending_choice', 'bling_api_required_selector',
    'bling_api_final_action', 'bling_api_manual_mapping_required', 'bling_api_must_run_ai_check',
)


def _audit(event: str, **details: object) -> None:
    payload = {'responsible_file': RESPONSIBLE_FILE, **details}
    add_audit_event(event, area='UNIVERSAL', status='OK', details=payload)


def _force_plain_context() -> None:
    for key in NO_API_KEYS:
        st.session_state.pop(key, None)
    set_entry_context(CONTEXT_UNIVERSAL)
    activate_csv_finish_mode()
    st.session_state['mapeiaai_flow_kind'] = 'universal_model_mapping'
    st.session_state['flow_kind'] = 'universal_model_mapping'
    st.session_state['api_flow_active'] = False
    st.session_state['mapear_planilha_sem_api_active'] = True
    st.session_state['mapeiaai_home_entry_path'] = 'mapear_modelo_sem_api'
    st.session_state['active_feature_mode'] = 'csv'
    st.session_state['active_feature_operation'] = 'universal'
    st.session_state['active_feature_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_operation'] = 'universal'
    st.session_state['flow_spine_final_destination'] = 'download'
    st.session_state['flow_spine_final_title'] = 'Download'
    st.session_state['flow_spine_primary_action_label'] = 'Download Modelo Mapeado'


def _is_universal_csv_context() -> bool:
    contract = active_contract()
    return contract.key in {'universal_csv', 'universal_mapping_csv', 'universal_mapping'} or (contract.mode == 'csv' and contract.operation == 'universal')


def _render_contract_guard() -> bool:
    if _is_universal_csv_context():
        return True
    contract = active_contract()
    st.warning('Este fluxo é exclusivo para Mapear planilha por contrato / Universal CSV.')
    st.caption(f'Contrato ativo atual: {contract.key}. Use o fluxo principal para {contract.label}.')
    add_audit_event('universal_flow_blocked_outside_universal_csv', area='UNIVERSAL', status='BLOQUEADO', details={'active_contract': contract.key, 'operation': contract.operation, 'mode': contract.mode, 'responsible_file': RESPONSIBLE_FILE})
    return False


def _read_upload(uploaded_file, *, allow_empty_rows: bool, file_role: str) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        df = read_uploaded_file(uploaded_file).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo: {exc}')
        return None
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        st.warning('Arquivo recebido, mas não encontrei colunas válidas. Confira o cabeçalho da planilha ou do arquivo enviado.')
        return None
    if df.empty and not allow_empty_rows:
        st.warning('Arquivo de origem recebido, mas não encontrei linhas de dados. A origem precisa ter produtos/linhas para preencher o modelo.')
        return None
    if df.empty and allow_empty_rows:
        st.info('Modelo aceito sem linhas de dados. Vou usar as colunas/layout como estrutura final e preencher com a origem na próxima etapa.')
        _audit('mapear_planilha_modelo_sem_linhas_aceito', file_role=file_role, columns=int(len(df.columns)), original_file_name=str(getattr(uploaded_file, 'name', '') or ''))
    return df


def _store_df(key: str, df: pd.DataFrame | None) -> None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        st.session_state[key] = df.copy().fillna('')


def _store_model_file(uploaded_file) -> None:
    if uploaded_file is None:
        return
    name = str(getattr(uploaded_file, 'name', '') or '').strip()
    try:
        data = uploaded_file.getvalue()
    except Exception:
        data = b''
    if name and data:
        st.session_state[UNIVERSAL_MODEL_FILE_NAME_KEY] = name
        st.session_state[UNIVERSAL_MODEL_FILE_BYTES_KEY] = bytes(data)


def _sync_legacy_universal_model_aliases(model: pd.DataFrame | None) -> None:
    """Mantém diagnósticos/guardas antigos alinhados ao modelo universal real.

    O fluxo independente usa `mapeiaai_universal_model_df` como fonte única.
    As chaves antigas abaixo existem apenas para compatibilidade e não podem
    nascer de modelo de estoque/cadastro/API.
    """
    if not isinstance(model, pd.DataFrame) or not len(model.columns):
        return
    clean = model.copy().fillna('')
    for key in LEGACY_UNIVERSAL_MODEL_KEYS:
        st.session_state[key] = clean
    st.session_state['home_model_operation_detected'] = 'universal'
    st.session_state['home_detected_operation'] = 'universal'


def _store_universal_source(df: pd.DataFrame | None, *, source_mode: str) -> None:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return
    clean = df.copy().fillna('')
    st.session_state[UNIVERSAL_SOURCE_KEY] = clean
    st.session_state['df_origem_unificada'] = clean
    st.session_state['mapeiaai_universal_source_kind'] = source_mode
    if source_mode == 'site':
        st.session_state['df_origem_site'] = clean
    elif source_mode == 'upload':
        st.session_state['df_origem_arquivo'] = clean


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
    return hashlib.sha256(f'{shape}:{columns}:{sample_hash}'.encode('utf-8')).hexdigest()[:16]


def _flow_signature(model: pd.DataFrame, source: pd.DataFrame, ai_enabled: bool, rules_enabled: bool) -> str:
    return f'{_df_signature(source)}:{_df_signature(model)}:ai={int(ai_enabled)}:rules={int(rules_enabled)}'


def _reset_universal_state_if_changed(model: pd.DataFrame, source: pd.DataFrame, ai_enabled: bool, rules_enabled: bool) -> str:
    signature = _flow_signature(model, source, ai_enabled, rules_enabled)
    previous = str(st.session_state.get(UNIVERSAL_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        for key in (UNIVERSAL_MAPPING_KEY, UNIVERSAL_OUTPUT_KEY, UNIVERSAL_ENGINE_KEY, 'neutral_mapping_state_v1', 'neutral_mapping_report_v1'):
            st.session_state.pop(key, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
        _audit('universal_flow_state_reset_by_signature_change', previous=previous, current=signature)
    st.session_state[UNIVERSAL_SIGNATURE_KEY] = signature
    return signature


def _progress_callback(progress_bar, status_box):
    def _callback(info: dict) -> None:
        progress = float(info.get('progress') or 0.0)
        progress_bar.progress(max(0.0, min(1.0, progress)), text=str(info.get('stage') or 'Processando'))
        status_box.caption(str(info.get('message') or ''))
    return _callback


def _render_model_step() -> pd.DataFrame | None:
    st.markdown('### 1. Anexar Modelo / Mapear')
    model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.caption('Anexe primeiro a planilha modelo exatamente no formato que você quer receber no final.')
        st.caption('A saída final preservará as colunas e a ordem desse modelo, preenchendo os dados vindos da origem escolhida depois.')
        st.caption(MODEL_UPLOAD_LABEL)
        uploaded = st.file_uploader('Planilha modelo final', type=None, key='mapeiaai_universal_model_upload')
        df = _read_upload(uploaded, allow_empty_rows=True, file_role='modelo')
        if isinstance(df, pd.DataFrame):
            _store_model_file(uploaded)
            _store_df(UNIVERSAL_MODEL_KEY, df)
            _sync_legacy_universal_model_aliases(df)
            _audit('mapear_planilha_modelo_anexado_primeiro', rows=int(len(df)), columns=int(len(df.columns)), original_file_name=str(getattr(uploaded, 'name', '') or ''), allow_empty_rows=True)
        model = _current_df(UNIVERSAL_MODEL_KEY)
    if not isinstance(model, pd.DataFrame):
        st.info('Envie a planilha modelo final para liberar a origem de dados, os toggles, o mapeamento, o preview e o download.')
        return None
    _sync_legacy_universal_model_aliases(model)
    st.success('Modelo final carregado. A saída seguirá exatamente essas colunas e essa ordem.')
    _audit('mapear_planilha_modelo_confirmado_primeiro', rows=int(len(model)), columns=int(len(model.columns)))
    st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
    st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
    return model


def _render_source_upload() -> pd.DataFrame | None:
    st.caption('Anexe a origem dos dados: fornecedor, marketplace, CSV, planilha, XML, MHTML ou PDF.')
    st.caption(SOURCE_UPLOAD_LABEL)
    uploaded = st.file_uploader('Arquivo de origem dos dados', type=None, key='mapeiaai_universal_source_upload')
    df = _read_upload(uploaded, allow_empty_rows=False, file_role='origem')
    if isinstance(df, pd.DataFrame):
        _store_universal_source(df, source_mode='upload')
        _audit('mapear_planilha_fonte_anexada', rows=int(len(df)), columns=int(len(df.columns)), source_mode='upload')
    return _current_df(UNIVERSAL_SOURCE_KEY)


def _render_source_site() -> pd.DataFrame | None:
    st.caption('Cole links de produtos, categorias ou buscas. A captura por site preencherá o modelo anexado na primeira etapa.')
    raw_urls = st.text_area('Links para buscar produtos por site', height=130, key='mapeiaai_universal_site_urls')
    all_products = st.checkbox('Buscar todos os produtos encontrados', value=True, key='mapeiaai_universal_site_all_products')
    if st.button('Buscar produtos por site', use_container_width=True, key='mapeiaai_universal_run_site'):
        if not str(raw_urls or '').strip():
            st.warning('Informe pelo menos um link para buscar por site.')
        else:
            progress_bar = st.progress(0, text='Preparando busca por site...')
            status_box = st.empty()
            try:
                df_site = run_site_pipeline(str(raw_urls), requested_columns=None, all_products=bool(all_products), operation='universal', progress_callback=_progress_callback(progress_bar, status_box))
                _store_universal_source(df_site, source_mode='site')
                _audit('mapear_planilha_fonte_site_carregada', rows=int(len(df_site)), columns=int(len(df_site.columns)), source_mode='site')
                st.success(f'Busca por site concluída: {len(df_site)} linha(s).')
            except Exception as exc:
                st.error(f'Falha ao buscar produtos por site: {exc}')
    return _current_df(UNIVERSAL_SOURCE_KEY)


def _render_source_step() -> pd.DataFrame | None:
    st.markdown('### 2. Origem de dados')
    st.caption('Agora escolha de onde virão os dados que serão inseridos no modelo anexado.')
    source_mode = st.radio('Como quer trazer os dados da origem?', [SOURCE_MODE_UPLOAD, SOURCE_MODE_SITE], key='mapeiaai_universal_source_mode')
    source = _render_source_site() if source_mode == SOURCE_MODE_SITE else _render_source_upload()
    if not isinstance(source, pd.DataFrame):
        st.info('Carregue a origem de dados para liberar os toggles, mapeamento, preview e download.')
        return None
    st.success(f'Origem carregada: {len(source)} linha(s) x {len(source.columns)} coluna(s).')
    _audit('mapear_planilha_fonte_confirmada', rows=int(len(source)), columns=int(len(source.columns)), source_mode=source_mode)
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
        st.markdown('##### Inteligência Artificial')
        mapping_ai = render_mapping_auto_decision_toggle(widget_key='mapeiaai_universal_toggle_mapping_auto', source='universal_flow', default=False, label='Mapeamento automático com IA')
        rules = st.toggle('Regras e recursos inteligentes no download', value=True, key='mapeiaai_universal_toggle_rules')
    st.session_state['mapeiaai_universal_toggle_mapping_ai'] = bool(mapping_ai)
    toggles = {'price': bool(price), 'category': bool(category), 'mapping_ai': bool(mapping_ai), 'rules': bool(rules)}
    _audit('mapear_planilha_toggles_definidos', **toggles, mapping_auto_user_decided=True)
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
    _audit('mapear_planilha_categorizacao_aplicada', total=int(stats.get('total', 0)), applied=int(applied), confidence_min=float(confidence))
    helper = [col for col in ('Categoria', 'categoria_sugerida_ia', 'acao_categoria_ia', 'confianca_categoria_ia', 'motivo_categoria_ia') if col in output.columns]
    if helper:
        st.dataframe(output[helper].head(30).astype(str), use_container_width=True, height=260)
    return output


def _render_ai_tools(source: pd.DataFrame, model: pd.DataFrame, enabled: bool) -> None:
    st.markdown('### 4. Inteligência Artificial')
    if not enabled:
        st.caption('Mapeamento automático desligado. O mapeamento começará vazio para escolha manual.')
        return
    if st.button('Regerar sugestão de mapeamento com IA', use_container_width=True, key='mapeiaai_universal_regen_ai_mapping'):
        suggested, engine = suggest_shared_mapping(source, model, operation='universal')
        st.session_state[UNIVERSAL_MAPPING_KEY] = suggested
        st.session_state[UNIVERSAL_ENGINE_KEY] = engine
        clear_shared_mapping_widgets('mapeiaai_universal')
        _audit('mapear_planilha_ia_mapeamento_regenerada', engine=engine, targets=int(len(suggested)))
        st.success('Sugestões de mapeamento atualizadas.')
        safe_rerun('universal_ai_mapping_regenerated')


def render_universal_flow() -> None:
    _force_plain_context()
    if not _render_contract_guard():
        return
    _audit('mapear_planilha_fluxo_aberto', order='modelo_primeiro_origem_depois', api=False)
    st.markdown('## Anexar Modelo / Mapear Planilha')
    st.caption('Sem API: anexe o modelo final, escolha a origem dos dados, use opcionais, revise o mapeamento, veja o preview e baixe a planilha idêntica.')
    model = _render_model_step()
    if not isinstance(model, pd.DataFrame):
        return
    source = _render_source_step()
    if not isinstance(source, pd.DataFrame):
        return
    toggles = _render_toggles()
    processed = source.copy().fillna('')
    if toggles['price']:
        processed = render_shared_calculator(processed, key_prefix='mapeiaai_universal', force_enabled=True)
        _audit('mapear_planilha_preco_processado', rows=int(len(processed)), columns=int(len(processed.columns)))
    else:
        st.caption('Preço desligado: valores mantidos como vieram da origem.')
    processed = _apply_category(processed, toggles['category'])
    signature = _reset_universal_state_if_changed(model, processed, toggles['mapping_ai'], toggles['rules'])
    if toggles['mapping_ai'] and str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or '') == 'manual_sem_ia':
        st.session_state.pop(UNIVERSAL_MAPPING_KEY, None)
        st.session_state.pop(UNIVERSAL_ENGINE_KEY, None)
        clear_shared_mapping_widgets('mapeiaai_universal')
    _render_ai_tools(processed, model, toggles['mapping_ai'])
    mapping = render_shared_contract_mapping(processed, model, signature=signature, mapping_state_key=UNIVERSAL_MAPPING_KEY, engine_state_key=UNIVERSAL_ENGINE_KEY, key_prefix='mapeiaai_universal', ai_enabled=toggles['mapping_ai'])
    mapping, _mapping_rows = build_and_sync_mapping(processed, model, mapping, operation='universal', signature=signature, engine=str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or 'local'), mapping_state_key=UNIVERSAL_MAPPING_KEY, engine_state_key=UNIVERSAL_ENGINE_KEY)
    _audit('mapear_planilha_mapeamento_renderizado', mapped_fields=int(sum(1 for value in mapping.values() if str(value or '').strip())), total_fields=int(len(mapping)), engine=str(st.session_state.get(UNIVERSAL_ENGINE_KEY) or 'local'))
    output = render_shared_final_csv(processed, model, mapping, key_prefix='mapeiaai_universal', file_name='mapeiaai_planilha_final_mapeada.csv', run_smart_features=toggles['rules'])
    if isinstance(output, pd.DataFrame):
        st.session_state[UNIVERSAL_OUTPUT_KEY] = output
        render_congratulations_success(area='UNIVERSAL', context='download_final_planilha_mapeada')
        _audit('mapear_planilha_preview_download_pronto', rows=int(len(output)), columns=int(len(output.columns)), csv=True, final_message='Congratulations Success')


__all__ = ['render_universal_flow']
