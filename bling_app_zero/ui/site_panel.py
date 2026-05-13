from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.instant_scraper import BrowserScraperConfig, run_browser_scraper
from bling_app_zero.flows.site_operation_router import config_for_site_operation, run_site_engine
from bling_app_zero.ui.guided_login_panel import render_guided_login_panel
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.site_models import choose_site_cadastro_model_df, choose_site_estoque_model_df, choose_site_model_df, render_optional_site_model_upload, requested_columns_for_site_capture
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _query_urls_default() -> str:
    return _query_param('urls') or _query_param('url')


def _current_site_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final', 'home_slim_flow_operation'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    flow = str(_query_param('flow') or _query_param('operacao') or '').strip().lower()
    if flow in {'estoque', 'estoque_site', 'stock', 'stock_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    return 'cadastro'


def _site_df_key(operation: str) -> str:
    return f'df_site_bruto_{operation}'


def _store_site_df(operation: str, df_site: pd.DataFrame) -> None:
    st.session_state[_site_df_key(operation)] = df_site
    st.session_state['df_site_bruto'] = df_site
    other = 'estoque' if operation == 'cadastro' else 'cadastro'
    st.session_state.pop(_site_df_key(other), None)


def _get_site_df(operation: str) -> pd.DataFrame | None:
    df_current = st.session_state.get(_site_df_key(operation))
    if isinstance(df_current, pd.DataFrame):
        return df_current
    df_legacy = st.session_state.get('df_site_bruto')
    legacy_operation = str(st.session_state.get('operation_site') or st.session_state.get('tipo_operacao_site') or '').strip().lower()
    if legacy_operation == operation and isinstance(df_legacy, pd.DataFrame):
        return df_legacy
    return None


def _has_columns(columns: list[str] | None) -> bool:
    return bool([str(column).strip() for column in (columns or [])])


def _orange_warning(message: str) -> None:
    st.markdown(f"""<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>""", unsafe_allow_html=True)


def _operation_badge(operation: str) -> str:
    if operation == 'estoque':
        return 'Motor ativo: ESTOQUE POR SITE - somente colunas do modelo de estoque.'
    return 'Motor ativo: CADASTRO POR SITE - origem completa para cadastro de produtos.'


def _guided_login_toggle_key(operation: str) -> str:
    return f'site_guided_login_enabled_{operation}'


def _guided_login_enabled(operation: str) -> bool:
    return bool(st.session_state.get(_guided_login_toggle_key(operation), False))


def _protected_session_value() -> str:
    key = 'guided_login_' + 'password_ephemeral'
    return str(st.session_state.get(key) or '').strip()


def _clear_stuck_capture(operation: str) -> None:
    _set_capture_state(
        operation=operation,
        running=False,
        finished=False,
        error='Captura anterior destravada manualmente. Execute novamente.',
    )
    add_audit_event(
        'site_capture_unstuck_manually',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE},
    )


def _render_guided_login_origin_module(operation: str) -> None:
    label = 'captura autenticada de estoque' if operation == 'estoque' else 'captura autenticada de cadastro'
    enabled = st.checkbox('Este fornecedor exige login?', value=_guided_login_enabled(operation), key=_guided_login_toggle_key(operation), help='Deixe desmarcado para busca normal por links.')
    if not enabled:
        st.caption('Busca pública ativa. O painel de login guiado fica escondido até você marcar esta opção.')
        return
    with st.expander('🔐 Configurar login guiado', expanded=True):
        st.caption(f'Use esta opção quando o fornecedor exigir entrada autenticada antes da {label}.')
        render_guided_login_panel()
    _orange_warning('Fornecedor com entrada autenticada detectada. A busca pública por links foi substituída pela captura estilo Instant Scraper.')


def _render_site_models_inline(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(operation)
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, operation)
    requested_columns = requested_columns_for_site_capture(operation, df_modelo_cadastro, df_modelo_estoque)
    if requested_columns:
        show_contract(requested_columns)
    elif operation == 'estoque':
        st.error('Para estoque por site, envie primeiro o modelo de estoque do Bling. A busca só será feita nas colunas desse modelo.')
    else:
        st.info('Sem modelo desta operação. Vou capturar os campos principais e deixar vazio o que não encontrar.')
    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input(operation: str) -> str:
    if _guided_login_enabled(operation):
        st.caption('Modo autenticado ativo. Use o botão de captura autenticada abaixo em vez da busca pública.')
        return ''
    return st.text_area('Links do fornecedor', value=_query_urls_default(), height=120, key=f'urls_site_{operation}', placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1', help='Cole um ou mais links: categoria, busca ou produtos individuais.')


def _set_capture_state(*, operation: str, running: bool, finished: bool, error: str = '', rows: int = 0, columns: int = 0) -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_finished'] = finished
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = operation
    st.session_state['site_capture_result_ready'] = bool(finished and not error and rows > 0)
    st.session_state['site_capture_rows'] = int(rows or 0)
    st.session_state['site_capture_columns'] = int(columns or 0)


def _run_authenticated_site_capture(operation: str, requested_columns: list[str] | None, df_modelo_cadastro: pd.DataFrame | None, df_modelo_estoque: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    entry_url = str(st.session_state.get('guided_login_url') or '').strip()
    user_value = str(st.session_state.get('guided_login_username') or '').strip()
    session_value = _protected_session_value()
    if not entry_url.startswith(('http://', 'https://')):
        _orange_warning('Informe uma URL de entrada válida antes de executar a captura autenticada.')
        return
    if not session_value:
        _orange_warning('Informe o valor protegido da sessão no painel de login guiado.')
        return
    if operation == 'estoque' and not _has_columns(requested_columns):
        _orange_warning('Busca autenticada bloqueada: carregue o modelo de estoque para definir as colunas solicitadas.')
        return

    started_at = time.time()
    completed = False
    progress = None
    _set_capture_state(operation=operation, running=True, finished=False)
    add_audit_event('authenticated_site_capture_started', area='SITE', step='entrada', details={'operation': operation, 'requested_columns_count': len(requested_columns or []), 'responsible_file': RESPONSIBLE_FILE, 'engine': 'BLING_INSTANT_SCRAPER'})

    try:
        progress = st.progress(0, text='Executando captura autenticada estilo Instant Scraper...')
        result = run_browser_scraper(BrowserScraperConfig(operation=operation, entry_url=entry_url, user_value=user_value, session_value=session_value, start_urls=[entry_url], model_columns=requested_columns or (list(df_modelo.columns) if isinstance(df_modelo, pd.DataFrame) else None), max_pages=25, max_products=300, allow_entry_step=True, security_resolved=bool(st.session_state.get('guided_login_security_resolved', False))))
        progress.progress(80, text='Organizando dados capturados...')
        for warning in result.warnings:
            _orange_warning(str(warning))
        if result.errors:
            error_message = '; '.join(result.errors)
            _set_capture_state(operation=operation, running=False, finished=False, error=error_message)
            add_audit_event('authenticated_site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'error': error_message, 'pages_visited': result.pages_visited, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
            _orange_warning(error_message)
            return
        if not isinstance(result.df, pd.DataFrame) or result.df.empty:
            error_message = 'A captura autenticada não encontrou dados na página.'
            _set_capture_state(operation=operation, running=False, finished=False, error=error_message)
            add_audit_event('authenticated_site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'pages_visited': result.pages_visited, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
            _orange_warning(error_message)
            return
        df_site = result.df.fillna('')
        save_site_source(df_site, entry_url, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
        _store_site_df(operation, df_site)
        st.session_state['operation_site'] = operation
        st.session_state['tipo_operacao_site'] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        st.session_state['origem_final'] = 'site'
        _set_capture_state(operation=operation, running=False, finished=True, rows=len(df_site), columns=len(df_site.columns))
        completed = True
        add_audit_event('authenticated_site_capture_saved_to_state', area='SITE', step='entrada', status='OK', details={'operation': operation, 'rows': len(df_site), 'columns': len(df_site.columns), 'pages_visited': result.pages_visited, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE, 'engine': 'BLING_INSTANT_SCRAPER'})
        if progress is not None:
            progress.progress(100, text='Captura autenticada concluída.')
        st.rerun()
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _set_capture_state(operation=operation, running=False, finished=False, error=message)
        add_audit_event('authenticated_site_capture_exception', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        _orange_warning('A captura autenticada falhou e foi destravada. Confira o log debug e tente novamente.')
    finally:
        if not completed and bool(st.session_state.get('site_capture_running')):
            _set_capture_state(operation=operation, running=False, finished=False, error=st.session_state.get('site_capture_error') or 'Captura interrompida antes de finalizar.')


def _run_site_capture(operation: str, raw_urls: str, requested_columns: list[str] | None, df_modelo_cadastro: pd.DataFrame | None, df_modelo_estoque: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    raw_urls = str(raw_urls or '').strip()
    if _guided_login_enabled(operation):
        _run_authenticated_site_capture(operation, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
        return
    if not raw_urls:
        st.warning('Informe pelo menos um link antes de iniciar a busca por site.')
        add_audit_event('site_capture_blocked_missing_urls', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    if operation == 'estoque' and not _has_columns(requested_columns):
        st.error('Busca bloqueada: carregue o modelo de estoque para definir exatamente quais colunas serão preenchidas.')
        add_audit_event('site_capture_blocked_missing_stock_model', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    started_at = time.time()
    st.session_state['site_capture_started_at'] = started_at
    _set_capture_state(operation=operation, running=True, finished=False)
    add_audit_event('site_capture_started', area='SITE', step='entrada', details={'operation': operation, 'requested_columns_count': len(requested_columns or []), 'has_cadastro_model': isinstance(df_modelo_cadastro, pd.DataFrame), 'has_estoque_model': isinstance(df_modelo_estoque, pd.DataFrame), 'responsible_file': RESPONSIBLE_FILE})
    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando produtos no site...')
    status_box = st.empty()
    try:
        df_site = run_site_engine(operation=operation, pipeline=load_site_pipeline(), raw_urls=raw_urls, requested_columns=requested_columns, all_products=True, max_pages=ALL_PAGES_LIMIT, max_products=ALL_PRODUCTS_LIMIT, progress_callback=make_site_progress_callback(progress_bar, status_box))
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _set_capture_state(operation=operation, running=False, finished=False, error=message)
        add_audit_event('site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        st.error('A busca por site não conseguiu finalizar. Baixe o log debug para conferir o erro técnico.')
        return
    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    _store_site_df(operation, df_site)
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = 'site'
    _set_capture_state(operation=operation, running=False, finished=True, rows=rows, columns=columns)
    add_audit_event('site_capture_saved_to_state', area='SITE', step='entrada', status='OK' if rows else 'AVISO', details={'operation': operation, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def render_site_panel() -> None:
    operation = _current_site_operation()
    if operation == 'estoque':
        from bling_app_zero.ui.estoque_site_panel import render_estoque_site_panel
        render_estoque_site_panel()
        return
    config = config_for_site_operation(operation)
    login_mode = _guided_login_enabled(operation)
    title = 'Captura autenticada guiada' if login_mode else 'Cole os links do fornecedor'
    text = 'Fornecedor com entrada autenticada: execute a captura estilo Instant Scraper.' if login_mode else 'A captura acontece aqui. Depois continue para a próxima etapa do Wizard.'
    st.markdown(f"""<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">{title}</h2><p class="bling-flow-card-text">{text}</p></section>""", unsafe_allow_html=True)
    st.info(_operation_badge(operation))
    st.caption(config.description)
    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input(operation)
    _render_guided_login_origin_module(operation)
    running = bool(st.session_state.get('site_capture_running'))
    if running:
        _orange_warning('Captura por site em andamento. Aguarde o preview da origem aparecer antes de continuar.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key=f'limpar_captura_travada_{operation}'):
            _clear_stuck_capture(operation)
            st.rerun()
    error = str(st.session_state.get('site_capture_error') or '').strip()
    if error:
        st.error(f'Última captura por site falhou: {error}')
    if _guided_login_enabled(operation):
        button_label = '🔐 Executar captura autenticada estilo Instant Scraper'
        button_disabled = running
    else:
        button_label = 'Buscar no site e gerar origem de cadastro'
        button_disabled = running or (operation == 'estoque' and not _has_columns(requested_columns))
    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        _run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
    df_site_bruto = _get_site_df(operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_site_source_summary(df_site_bruto, operation, show_history=False)
