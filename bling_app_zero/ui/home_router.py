from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_INTAKE_MODEL_KEY = 'mapeiaai_home_intake_model_df'
HOME_INTAKE_MODEL_FILE_KEY = 'mapeiaai_home_intake_model_file'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'

CADASTRO_MODEL_KEYS = ('home_modelo_cadastro_df', 'df_modelo_cadastro', 'modelo_cadastro_df')
ESTOQUE_MODEL_KEYS = ('home_modelo_estoque_df', 'df_modelo_estoque', 'modelo_estoque_df')
CADASTRO_SOURCE_KEY = 'home_modelo_cadastro_source'
ESTOQUE_SOURCE_KEY = 'home_modelo_estoque_source'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_ORIGEM = 'origem'

VALID_INTAKE_EXTENSIONS = ('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb', '.html', '.htm', '.mht', '.mhtml', '.xml', '.pdf')
INVALID_DIAGNOSTIC_EXTENSIONS = ('.zip', '.txt', '.log', '.json')


def _model_has_columns(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _set_flow(flow: str) -> None:
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    if flow == FLOW_WIZARD:
        st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
    add_audit_event(
        'home_model_contract_received',
        area='HOME',
        details={'previous': previous, 'selected': flow, 'next_step': st.session_state.get(WIZARD_STEP_KEY), 'cadastro_estoque_step_removed': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operation_v2'] = flow
        if flow == FLOW_WIZARD:
            st.query_params['step'] = STEP_ORIGEM
    except Exception:
        pass
    st.rerun()


def _clear_flow_query_param() -> None:
    for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _current_flow() -> str:
    allowed = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if not flow:
        try:
            flow = str(st.query_params.get('operation_v2') or '').strip()
        except Exception:
            flow = ''
        if flow:
            st.session_state[ACTIVE_FLOW_KEY] = flow
            st.session_state[HOME_ALLOW_FLOW_KEY] = True
            allowed = True

    if allowed and flow:
        if flow in {FLOW_WIZARD, FLOW_PRICE_UPDATE}:
            return flow
        return FLOW_WIZARD

    stale_flow = st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    if stale_flow:
        add_audit_event(
            'home_stale_flow_cleared',
            area='HOME',
            details={'reason': 'home_must_start_on_sheet_contract_upload', 'stale_flow': stale_flow, 'responsible_file': RESPONSIBLE_FILE},
        )
    return ''


def _uploaded_name(uploaded_file) -> str:
    return str(getattr(uploaded_file, 'name', 'arquivo') or 'arquivo').strip()


def _file_extension(file_name: str) -> str:
    name = str(file_name or '').strip().lower()
    if '.' not in name:
        return ''
    return name[name.rfind('.'):]


def _saved_intake_model() -> tuple[pd.DataFrame | None, str]:
    df = st.session_state.get(HOME_INTAKE_MODEL_KEY)
    file_name = str(st.session_state.get(HOME_INTAKE_MODEL_FILE_KEY) or 'planilha recebida').strip()
    if _model_has_columns(df):
        return df.copy().fillna(''), file_name
    return None, file_name


def _clear_saved_intake_model() -> None:
    for key in (
        HOME_INTAKE_MODEL_KEY,
        HOME_INTAKE_MODEL_FILE_KEY,
        'mapeiaai_final_contract_df',
        'mapeiaai_home_intake_model_type',
        'mapeiaai_home_intake_model_confidence',
    ):
        st.session_state.pop(key, None)
    for key in CADASTRO_MODEL_KEYS + ESTOQUE_MODEL_KEYS:
        st.session_state.pop(key, None)
    for key in (
        CADASTRO_SOURCE_KEY,
        ESTOQUE_SOURCE_KEY,
        'home_detected_operation',
        'home_slim_flow_operation',
        'operacao_final',
        'tipo_operacao_final',
        'tipo_operacao_site',
        'operation_site',
    ):
        st.session_state.pop(key, None)
    add_audit_event('home_contract_model_cleared', area='HOME', details={'responsible_file': RESPONSIBLE_FILE})


def _read_intake_file(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    file_name = _uploaded_name(uploaded_file)
    extension = _file_extension(file_name)
    if extension in INVALID_DIAGNOSTIC_EXTENSIONS or (extension and extension not in VALID_INTAKE_EXTENSIONS):
        st.warning(
            'Arquivo recebido, mas ele não é uma planilha/modelo de destino válido. '
            'Envie CSV, Excel, HTML/MHTML, XML ou PDF. ZIP, TXT e logs servem apenas para diagnóstico.'
        )
        add_audit_event(
            'home_contract_invalid_extension_blocked',
            area='HOME',
            status='BLOQUEADO',
            details={'file_name': file_name, 'extension': extension or 'sem_extensao', 'responsible_file': RESPONSIBLE_FILE},
        )
        return None

    try:
        df = read_upload_fast(uploaded_file)
    except Exception as exc:
        st.error(f'Não consegui ler essa planilha: {exc}')
        add_audit_event(
            'home_contract_read_failed',
            area='HOME',
            status='ERRO',
            details={'file_name': file_name, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
        )
        return None

    # BLINGFIX: modelo de destino pode ter somente cabeçalho e zero linhas.
    # Para liberar o fluxo, o que importa é existir contrato de colunas.
    if not _model_has_columns(df):
        st.warning(
            'Arquivo recebido, mas não encontrei colunas válidas para mapear. '
            'Confira se a primeira linha tem cabeçalhos.'
        )
        add_audit_event(
            'home_contract_without_columns_blocked',
            area='HOME',
            status='BLOQUEADO',
            details={'file_name': file_name, 'extension': extension or 'sem_extensao', 'responsible_file': RESPONSIBLE_FILE},
        )
        return None

    if df.empty:
        add_audit_event(
            'home_contract_header_only_accepted',
            area='HOME',
            status='OK',
            details={'file_name': file_name, 'extension': extension or 'sem_extensao', 'columns_count': int(len(df.columns)), 'rows_count': 0, 'responsible_file': RESPONSIBLE_FILE},
        )

    return df.fillna('')


def _write_model_keys(keys: tuple[str, ...], df: pd.DataFrame, *, source_key: str) -> None:
    clean_df = df.copy().fillna('')
    for key in keys:
        st.session_state[key] = clean_df.copy().fillna('')
    st.session_state[source_key] = 'upload'


def _store_contract_model(df: pd.DataFrame, file_name: str) -> None:
    clean_df = df.copy().fillna('')

    st.session_state[HOME_INTAKE_MODEL_KEY] = clean_df
    st.session_state[HOME_INTAKE_MODEL_FILE_KEY] = file_name
    st.session_state['mapeiaai_final_contract_df'] = clean_df

    # Modelo neutro: serve como contrato de colunas, sem pedir Cadastro/Estoque ao usuário.
    _write_model_keys(CADASTRO_MODEL_KEYS, clean_df, source_key=CADASTRO_SOURCE_KEY)
    _write_model_keys(ESTOQUE_MODEL_KEYS, clean_df, source_key=ESTOQUE_SOURCE_KEY)

    for key in (
        'mapeiaai_home_intake_model_type',
        'mapeiaai_home_intake_model_confidence',
        'home_detected_operation',
        'home_slim_flow_operation',
        'operacao_final',
        'tipo_operacao_final',
        'tipo_operacao_site',
        'operation_site',
    ):
        st.session_state.pop(key, None)

    try:
        st.query_params.pop('operacao', None)
    except Exception:
        pass

    add_audit_event(
        'home_contract_model_saved_without_operation_choice',
        area='HOME',
        details={'file_name': file_name, 'columns_count': int(len(clean_df.columns)), 'rows_count': int(len(clean_df)), 'cadastro_estoque_step_removed': True, 'responsible_file': RESPONSIBLE_FILE},
    )


def _render_contract_preview(df: pd.DataFrame, file_name: str) -> None:
    st.success('Planilha recebida como modelo de destino.')
    if df.empty:
        st.caption('Modelo sem linhas aceito: ele será usado como contrato de colunas para o arquivo final.')
    st.caption('O próximo passo será escolher a origem dos dados. Não há mais escolha manual entre Cadastro e Estoque.')
    st.caption(f'Arquivo: {file_name} · {len(df.columns)} coluna(s) · {len(df)} linha(s)')
    with st.expander('Conferir colunas da planilha', expanded=False):
        preview_df = df.head(8).astype(str) if not df.empty else pd.DataFrame(columns=list(df.columns))
        st.dataframe(preview_df, use_container_width=True, height=220)
        st.caption(', '.join(map(str, df.columns)))

    col_continue, col_clear = st.columns(2)
    with col_continue:
        if st.button('Continuar para origem dos dados', use_container_width=True, key='home_continue_after_contract_upload'):
            add_audit_event(
                'home_contract_continue_clicked',
                area='HOME',
                details={'file_name': file_name, 'columns_count': int(len(df.columns)), 'rows_count': int(len(df)), 'flow': FLOW_WIZARD, 'detection_disabled': True, 'next_step': STEP_ORIGEM, 'cadastro_estoque_step_removed': True, 'responsible_file': RESPONSIBLE_FILE},
            )
            _set_flow(FLOW_WIZARD)
    with col_clear:
        if st.button('Limpar e anexar outro', use_container_width=True, key='home_clear_contract_upload'):
            _clear_saved_intake_model()
            st.rerun()


def _render_operation_choice() -> None:
    st.markdown('## O que você quer mapear hoje?')
    st.caption(
        'Anexe o modelo de destino. O sistema usa as colunas desse arquivo como contrato final, '
        'sem exigir escolha manual entre Cadastro e Estoque.'
    )

    uploaded = st.file_uploader(
        'Planilha/modelo de destino',
        type=None,
        accept_multiple_files=False,
        key='home_single_model_intake_upload',
        help='No celular o seletor fica livre para evitar bloqueio falso de CSV/planilhas válidas. A validação acontece dentro do MapeiaAI.',
    )

    if uploaded is None:
        saved_df, saved_file_name = _saved_intake_model()
        if isinstance(saved_df, pd.DataFrame):
            add_audit_event(
                'home_contract_model_reused_from_session',
                area='HOME',
                details={'file_name': saved_file_name, 'columns_count': int(len(saved_df.columns)), 'rows_count': int(len(saved_df)), 'responsible_file': RESPONSIBLE_FILE},
            )
            _render_contract_preview(saved_df, saved_file_name)
            return
        st.info('Anexe a planilha ou modelo de destino para liberar o próximo passo.')
        st.caption('Depois disso você escolhe a origem dos dados, faz o mapeamento, confere o preview e baixa o arquivo final.')
        return

    df = _read_intake_file(uploaded)
    if not isinstance(df, pd.DataFrame):
        saved_df, saved_file_name = _saved_intake_model()
        if isinstance(saved_df, pd.DataFrame):
            st.info('Mantive o último modelo válido salvo. Você pode continuar com ele ou limpar e anexar outro.')
            _render_contract_preview(saved_df, saved_file_name)
            return
        st.info('Anexe uma planilha/modelo válido para liberar o próximo passo.')
        st.caption('Formatos aceitos: CSV, Excel, HTML/MHTML, XML ou PDF. ZIP/TXT/log não são modelos de destino.')
        return

    file_name = _uploaded_name(uploaded)
    _store_contract_model(df, file_name)
    add_audit_event(
        'home_contract_model_uploaded',
        area='HOME',
        details={'file_name': file_name, 'columns_count': int(len(df.columns)), 'rows_count': int(len(df)), 'flow': FLOW_WIZARD, 'detection_disabled': True, 'cadastro_estoque_step_removed': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    _render_contract_preview(df, file_name)


def _back_to_operations() -> None:
    st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    add_audit_event('home_contract_flow_cleared', area='HOME', details={'kept_contract': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _render_back_to_operations() -> None:
    if st.button('← Voltar', use_container_width=True, key='home_back_to_operation_choice'):
        _back_to_operations()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    _render_back_to_operations()
    if flow == FLOW_PRICE_UPDATE:
        render_price_multistore_v2()
        return

    if flow != FLOW_WIZARD:
        st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD

    render_home_wizard()


__all__ = ['FLOW_PRICE_UPDATE', 'FLOW_WIZARD', 'render_home_router']
