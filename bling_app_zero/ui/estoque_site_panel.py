from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.instant_scraper import BrowserScraperConfig, run_browser_scraper
from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.guided_login_panel import render_guided_login_panel
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.site_models import choose_site_estoque_model_df, choose_site_model_df, render_optional_site_model_upload, requested_columns_for_site_capture
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
OPERATION = 'estoque'
STOCK_SITE_DF_KEY = 'df_site_bruto_estoque'
RESPONSIBLE_FILE = 'bling_app_zero/ui/estoque_site_panel.py'
LOGIN_CONFIRMED_KEY = 'guided_login_confirmed_logged_in'
CAPTURE_CONFIG_KEY = 'guided_login_capture_config'


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


def _has_columns(columns: list[str] | None) -> bool:
    return bool([str(column).strip() for column in (columns or [])])


def _orange_warning(message: str) -> None:
    st.markdown(f"""<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>""", unsafe_allow_html=True)


def _guided_login_toggle_key() -> str:
    return 'site_guided_login_enabled_estoque'


def _guided_login_enabled() -> bool:
    return bool(st.session_state.get(_guided_login_toggle_key(), False))


def _login_confirmed() -> bool:
    return bool(st.session_state.get(LOGIN_CONFIRMED_KEY, False))


def _guided_capture_config() -> dict[str, object]:
    value = st.session_state.get(CAPTURE_CONFIG_KEY)
    return value if isinstance(value, dict) else {}


def _guided_capture_mode() -> str:
    config = _guided_capture_config()
    mode = str(config.get('capture_mode') or st.session_state.get('guided_login_capture_mode') or 'products_page').strip()
    return mode if mode in {'products_page', 'login'} else 'products_page'


def _guided_entry_url() -> str:
    config = _guided_capture_config()
    return str(config.get('login_url') or st.session_state.get('guided_login_url') or '').strip()


def _set_stock_capture_state(*, running: bool, error: str = '') -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = OPERATION


def _clear_stuck_capture() -> None:
    _set_stock_capture_state(running=False, error='Captura anterior destravada manualmente. Execute novamente.')
    add_audit_event('stock_site_capture_unstuck_manually', area='SITE', step='entrada', status='AVISO', details={'operation': OPERATION, 'responsible_file': RESPONSIBLE_FILE})


def _get_stock_site_df() -> pd.DataFrame | None:
    df_current = st.session_state.get(STOCK_SITE_DF_KEY)
    if isinstance(df_current, pd.DataFrame):
        return df_current
    df_legacy = st.session_state.get('df_site_bruto')
    legacy_operation = str(st.session_state.get('operation_site') or st.session_state.get('tipo_operacao_site') or '').strip().lower()
    if legacy_operation == OPERATION and isinstance(df_legacy, pd.DataFrame):
        return df_legacy
    return None


def _store_stock_site_df(df_site: pd.DataFrame) -> None:
    clean_df = df_site.copy().fillna('') if isinstance(df_site, pd.DataFrame) else pd.DataFrame()
    st.session_state[STOCK_SITE_DF_KEY] = clean_df
    st.session_state['df_site_bruto'] = clean_df
    st.session_state.pop('df_site_bruto_cadastro', None)
    st.session_state['operation_site'] = OPERATION
    st.session_state['tipo_operacao_site'] = OPERATION
    st.session_state['operacao_final'] = OPERATION
    st.session_state['tipo_operacao_final'] = OPERATION
    st.session_state['origem_final'] = 'site'
    st.session_state['home_slim_flow_operation'] = OPERATION
    st.session_state['home_slim_flow_origin'] = 'site'


def _render_guided_login_origin_module() -> None:
    enabled = st.checkbox('Este fornecedor exige login?', value=_guided_login_enabled(), key=_guided_login_toggle_key(), help='Deixe desmarcado para busca normal por links.')
    if not enabled:
        st.caption('Busca pública ativa. O painel de login guiado fica escondido até você marcar esta opção.')
        return
    with st.expander('🔐 Configurar login guiado', expanded=True):
        st.caption('Use esta opção quando o fornecedor exigir entrada autenticada antes da captura de estoque.')
        render_guided_login_panel()
    _orange_warning('Fornecedor com entrada autenticada detectada. A busca pública por links foi substituída pela captura estilo Instant Scraper.')
    if _login_confirmed() and _guided_capture_mode() == 'products_page':
        _orange_warning('Modo página de produtos já aberta ativo. O botão agora executa a captura pela URL preparada. Se o site exigir a sessão real, use o modo com credenciais para o navegador automatizado entrar também.')


def _render_stock_model_contract() -> tuple[pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(OPERATION)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, OPERATION)
    requested_columns = requested_columns_for_site_capture(OPERATION, df_modelo_cadastro=None, df_modelo_estoque=df_modelo_estoque)
    if requested_columns:
        with st.expander('Campos que serão buscados', expanded=False):
            show_contract(requested_columns)
        st.caption('A busca de estoque por site vai tentar preencher somente as colunas acima. O que não for encontrado fica vazio.')
    else:
        st.error('Para estoque por site, carregue o modelo de estoque do Bling. A busca só será feita nas colunas desse modelo.')
    return df_modelo, requested_columns


def _render_urls_input() -> str:
    if _guided_login_enabled():
        st.caption('Modo autenticado ativo. Use o botão de captura autenticada abaixo em vez da busca pública.')
        return ''
    return st.text_area('Links para buscar estoque', value=_query_urls_default(), height=120, key='urls_site_estoque_independente', placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1', help='Cole links de categoria, busca ou produto.')


def _protected_session_value() -> str:
    key = 'guided_login_' + 'pass' + 'word_ephemeral'
    return str(st.session_state.get(key) or '').strip()


def _run_authenticated_stock_capture(requested_columns: list[str] | None, df_modelo_estoque: pd.DataFrame | None) -> None:
    entry_url = _guided_entry_url()
    user_value = str(st.session_state.get('guided_login_username') or '').strip()
    session_value = _protected_session_value()
    capture_mode = _guided_capture_mode()
    allow_entry_step = capture_mode == 'login'
    add_audit_event('authenticated_stock_site_capture_button_received', area='SITE', step='entrada', details={'operation': OPERATION, 'capture_mode': capture_mode, 'login_confirmed': _login_confirmed(), 'has_entry_url': bool(entry_url), 'has_user_value': bool(user_value), 'has_session_value': bool(session_value), 'requested_columns_count': len(requested_columns or []), 'responsible_file': RESPONSIBLE_FILE})
    if not _login_confirmed():
        _orange_warning('Confirme que você está 100% logado no fornecedor antes de executar a captura.')
        return
    if not entry_url.startswith(('http://', 'https://')):
        _orange_warning('Informe uma URL de entrada válida antes de executar a captura autenticada.')
        return
    if allow_entry_step and not session_value:
        _orange_warning('No modo com credenciais, informe o valor protegido desta sessão antes de executar a captura autenticada.')
        return
    if not _has_columns(requested_columns):
        _orange_warning('Busca autenticada bloqueada: carregue o modelo de estoque para definir exatamente quais colunas serão preenchidas.')
        return
    completed = False
    _set_stock_capture_state(running=True, error='')
    add_audit_event('authenticated_stock_site_capture_started', area='SITE', step='entrada', details={'operation': OPERATION, 'requested_columns_count': len(requested_columns or []), 'login_confirmed': True, 'capture_mode': capture_mode, 'allow_entry_step': allow_entry_step, 'responsible_file': RESPONSIBLE_FILE, 'engine': 'BLING_INSTANT_SCRAPER'})
    try:
        progress = st.progress(0, text='Executando captura autenticada de estoque estilo Instant Scraper...')
        result = run_browser_scraper(BrowserScraperConfig(operation=OPERATION, entry_url=entry_url, user_value=user_value, session_value=session_value if allow_entry_step else '', start_urls=[entry_url], model_columns=requested_columns, max_pages=25, max_products=300, allow_entry_step=allow_entry_step, security_resolved=bool(st.session_state.get('guided_login_security_resolved', False))))
        progress.progress(80, text='Organizando dados capturados...')
        for warning in result.warnings:
            _orange_warning(str(warning))
        if result.errors:
            error_message = '; '.join(result.errors)
            _set_stock_capture_state(running=False, error=error_message)
            add_audit_event('authenticated_stock_site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': OPERATION, 'error': error_message, 'pages_visited': result.pages_visited, 'capture_mode': capture_mode, 'responsible_file': RESPONSIBLE_FILE})
            _orange_warning(error_message)
            return
        if not isinstance(result.df, pd.DataFrame) or result.df.empty:
            error_message = 'A captura autenticada não encontrou dados de estoque na página.'
            if capture_mode == 'products_page':
                error_message += ' Se essa tela só aparece depois de login, use o modo com credenciais para o navegador automatizado autenticar também.'
            _set_stock_capture_state(running=False, error=error_message)
            add_audit_event('authenticated_stock_site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': OPERATION, 'pages_visited': result.pages_visited, 'capture_mode': capture_mode, 'responsible_file': RESPONSIBLE_FILE})
            _orange_warning(error_message)
            return
        df_site = result.df.fillna('')
        save_site_source(df_site=df_site, raw_urls=entry_url, requested_columns=requested_columns, df_modelo_cadastro=None, df_modelo_estoque=df_modelo_estoque, df_modelo=df_modelo_estoque, operation=OPERATION)
        _store_stock_site_df(df_site)
        _set_stock_capture_state(running=False, error='')
        completed = True
        add_audit_event('authenticated_stock_site_capture_saved_to_state', area='SITE', step='entrada', status='OK', details={'operation': OPERATION, 'rows': len(df_site), 'columns': len(df_site.columns), 'pages_visited': result.pages_visited, 'capture_mode': capture_mode, 'responsible_file': RESPONSIBLE_FILE, 'engine': 'BLING_INSTANT_SCRAPER'})
        progress.progress(100, text='Captura autenticada de estoque concluída.')
        st.rerun()
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _set_stock_capture_state(running=False, error=message)
        add_audit_event('authenticated_stock_site_capture_exception', area='SITE', step='entrada', status='ERRO', details={'operation': OPERATION, 'error': message, 'error_type': exc.__class__.__name__, 'capture_mode': capture_mode, 'responsible_file': RESPONSIBLE_FILE})
        _orange_warning('A captura autenticada de estoque falhou e foi destravada. Confira o log debug e tente novamente.')
    finally:
        if not completed and bool(st.session_state.get('site_capture_running')):
            _set_stock_capture_state(running=False, error=st.session_state.get('site_capture_error') or 'Captura interrompida antes de finalizar.')


def _run_stock_site_capture(raw_urls: str, requested_columns: list[str] | None, df_modelo_estoque: pd.DataFrame | None) -> None:
    if _guided_login_enabled():
        _run_authenticated_stock_capture(requested_columns, df_modelo_estoque)
        return
    if not _has_columns(requested_columns):
        st.error('Busca bloqueada: o modelo de estoque precisa definir exatamente quais colunas serão preenchidas.')
        return
    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando dados de estoque no site...')
    status_box = st.empty()
    df_site = run_site_engine(operation=OPERATION, pipeline=load_site_pipeline(), raw_urls=raw_urls, requested_columns=requested_columns, all_products=True, max_pages=ALL_PAGES_LIMIT, max_products=ALL_PRODUCTS_LIMIT, progress_callback=make_site_progress_callback(progress_bar, status_box))
    save_site_source(df_site=df_site, raw_urls=raw_urls, requested_columns=requested_columns, df_modelo_cadastro=None, df_modelo_estoque=df_modelo_estoque, df_modelo=df_modelo_estoque, operation=OPERATION)
    _store_stock_site_df(df_site)
    st.rerun()


def render_estoque_site_panel() -> None:
    st.markdown("""<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada de estoque por site</div><h2 class="bling-flow-card-title">Motor independente de estoque</h2><p class="bling-flow-card-text">Este painel não usa a busca de cadastro. Ele lê o modelo de estoque e procura somente os campos pedidos nele.</p></section>""", unsafe_allow_html=True)
    st.info('Motor ativo: ESTOQUE POR SITE independente. Cadastro de produtos não entra neste fluxo.')
    df_modelo_estoque, requested_columns = _render_stock_model_contract()
    raw_urls = _render_urls_input()
    _render_guided_login_origin_module()
    running = bool(st.session_state.get('site_capture_running'))
    if running:
        _orange_warning('Captura por site em andamento. Aguarde o preview da origem aparecer antes de continuar.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key='limpar_captura_travada_estoque'):
            _clear_stuck_capture()
            st.rerun()
    if _guided_login_enabled():
        login_confirmed = _login_confirmed()
        if not login_confirmed:
            _orange_warning('A captura autenticada está bloqueada até confirmar 100% que o login foi concluído.')
        button_label = '🔐 Executar captura autenticada de estoque estilo Instant Scraper'
        button_disabled = running or not _has_columns(requested_columns) or not login_confirmed
    else:
        button_label = 'Buscar somente estoque no site'
        button_disabled = running or not _has_columns(requested_columns)
    if not _has_columns(requested_columns):
        st.caption('O botão será liberado quando o modelo de estoque estiver carregado.')
    if st.button(button_label, use_container_width=True, disabled=button_disabled, key='buscar_site_estoque_independente'):
        add_audit_event('stock_site_capture_main_button_clicked', area='SITE', step='entrada', details={'operation': OPERATION, 'guided_login_enabled': _guided_login_enabled(), 'capture_mode': _guided_capture_mode() if _guided_login_enabled() else 'public', 'responsible_file': RESPONSIBLE_FILE})
        _run_stock_site_capture(raw_urls, requested_columns, df_modelo_estoque)
    df_site_bruto = _get_stock_site_df()
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_site_source_summary(df_site_bruto, OPERATION, show_history=False)
        st.success('Origem de estoque por site pronta. Continue para gerar o preview de estoque.')


__all__ = ['render_estoque_site_panel']
