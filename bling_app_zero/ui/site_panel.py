from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.instant_scraper import BrowserScraperConfig, run_browser_scraper
from bling_app_zero.flows.site_operation_router import config_for_site_operation, run_site_engine
from bling_app_zero.ui.guided_login_panel import render_guided_login_panel
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.manual_table_import_panel import render_manual_table_import_panel
from bling_app_zero.ui.site_models import (
    choose_site_cadastro_model_df,
    choose_site_estoque_model_df,
    choose_site_model_df,
    render_optional_site_model_upload,
    requested_columns_for_site_capture,
)
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'
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


def _clear_site_df(operation: str, reason: str) -> None:
    """Remove origem antiga da operação quando uma nova captura não é válida."""
    removed: list[str] = []
    current_key = _site_df_key(operation)
    for key in (current_key, 'df_site_bruto'):
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    add_audit_event(
        'site_capture_stale_source_cleared',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={'operation': operation, 'reason': reason, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
    )


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
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _finish_progress(progress, status_box=None, text: str = 'Captura encerrada.') -> None:
    """Finaliza e remove barras/caixas para não parecer processamento infinito."""
    if progress is not None:
        try:
            progress.progress(100, text=text)
            time.sleep(0.15)
            progress.empty()
        except Exception:
            pass
    if status_box is not None:
        try:
            status_box.empty()
        except Exception:
            pass


def _operation_badge(operation: str) -> str:
    if operation == 'estoque':
        return 'Motor ativo: ESTOQUE POR SITE - somente colunas do modelo de estoque.'
    return 'Motor ativo: CADASTRO POR SITE - origem completa para cadastro de produtos.'


def _guided_login_toggle_key(operation: str) -> str:
    return f'site_guided_login_enabled_{operation}'


def _guided_login_enabled(operation: str) -> bool:
    return bool(st.session_state.get(_guided_login_toggle_key(operation), False))


def _login_confirmed() -> bool:
    return bool(st.session_state.get(LOGIN_CONFIRMED_KEY, False))


def _guided_capture_config() -> dict[str, object]:
    value = st.session_state.get(CAPTURE_CONFIG_KEY)
    return value if isinstance(value, dict) else {}


def _guided_capture_mode() -> str:
    return 'browser_session'


def _guided_entry_url() -> str:
    config = _guided_capture_config()
    return str(config.get('supplier_url') or config.get('login_url') or st.session_state.get('guided_login_url') or '').strip()


def _clear_stuck_capture(operation: str) -> None:
    _clear_site_df(operation, 'captura_travada_limpa_manualmente')
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
    enabled = st.checkbox(
        'Este fornecedor exige login?',
        value=_guided_login_enabled(operation),
        key=_guided_login_toggle_key(operation),
        help='Deixe desmarcado para busca normal por links.',
    )
    if not enabled:
        st.caption('Busca pública ativa. O navegador do fornecedor fica escondido até você marcar esta opção.')
        return
    with st.expander('🔐 Navegador do fornecedor', expanded=True):
        st.caption(f'Faça login diretamente no site do fornecedor e abra a página de produtos antes da {label}.')
        render_guided_login_panel()
    _orange_warning('Fornecedor com entrada autenticada detectada. A busca pública por links foi substituída pela captura pelo navegador do fornecedor.')


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
        st.caption('Modo autenticado ativo. Use o navegador do fornecedor e o botão de captura autenticada abaixo em vez da busca pública.')
        return ''
    return st.text_area(
        'Links do fornecedor',
        value=_query_urls_default(),
        height=120,
        key=f'urls_site_{operation}',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole um ou mais links: categoria, busca ou produtos individuais.',
    )


def _set_capture_state(*, operation: str, running: bool, finished: bool, error: str = '', rows: int = 0, columns: int = 0) -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_finished'] = finished
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = operation
    st.session_state['site_capture_result_ready'] = bool(finished and not error and rows > 0)
    st.session_state['site_capture_rows'] = int(rows or 0)
    st.session_state['site_capture_columns'] = int(columns or 0)


def _render_universal_fallback(
    *,
    operation: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    if not _guided_login_enabled(operation):
        return
    expanded = bool(st.session_state.get('site_capture_error'))
    with st.expander('🧩 Compatibilidade universal para todos os fornecedores', expanded=expanded):
        _orange_warning(
            'Use esta opção quando o fornecedor bloquear iframe, popup, sessão, captcha, Cloudflare ou robô. '
            'Assim o fluxo continua funcionando: exporte, salve ou copie a tabela/lista do fornecedor e importe aqui.'
        )
        render_manual_table_import_panel(
            operation=operation,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )


def _run_authenticated_site_capture(
    operation: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    entry_url = _guided_entry_url()
    capture_mode = _guided_capture_mode()
    add_audit_event(
        'authenticated_site_capture_button_received',
        area='SITE',
        step='entrada',
        details={
            'operation': operation,
            'capture_mode': capture_mode,
            'login_confirmed': _login_confirmed(),
            'has_entry_url': bool(entry_url),
            'requested_columns_count': len(requested_columns or []),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if not _login_confirmed():
        _orange_warning('Confirme que você está logado no fornecedor e vendo a página de produtos antes de executar a captura.')
        return
    if not entry_url.startswith(('http://', 'https://')):
        _orange_warning('Informe uma URL válida do fornecedor antes de executar a captura autenticada.')
        return
    if operation == 'estoque' and not _has_columns(requested_columns):
        _orange_warning('Busca autenticada bloqueada: carregue o modelo de estoque para definir as colunas solicitadas.')
        return

    started_at = time.time()
    completed = False
    progress = None
    _set_capture_state(operation=operation, running=True, finished=False)
    add_audit_event(
        'authenticated_site_capture_started',
        area='SITE',
        step='entrada',
        details={
            'operation': operation,
            'requested_columns_count': len(requested_columns or []),
            'login_confirmed': True,
            'capture_mode': capture_mode,
            'allow_entry_step': False,
            'responsible_file': RESPONSIBLE_FILE,
            'engine': 'BLING_INSTANT_SCRAPER',
        },
    )
    try:
        progress = st.progress(0, text='Executando captura autenticada pelo navegador do fornecedor...')
        result = run_browser_scraper(
            BrowserScraperConfig(
                operation=operation,
                entry_url=entry_url,
                start_urls=[entry_url],
                model_columns=requested_columns or (list(df_modelo.columns) if isinstance(df_modelo, pd.DataFrame) else None),
                max_pages=25,
                max_products=300,
                allow_entry_step=False,
                security_resolved=True,
                persist_state=True,
                state_namespace=f'{operation}_supplier_browser',
            )
        )
        progress.progress(80, text='Organizando dados capturados...')
        for warning in result.warnings:
            _orange_warning(str(warning))
        if result.errors:
            error_message = '; '.join(result.errors)
            _clear_site_df(operation, 'captura_autenticada_com_erros')
            _set_capture_state(operation=operation, running=False, finished=False, error=error_message)
            _finish_progress(progress, text='Captura encerrada com erro.')
            add_audit_event(
                'authenticated_site_capture_failed',
                area='SITE',
                step='entrada',
                status='ERRO',
                details={
                    'operation': operation,
                    'error': error_message,
                    'pages_visited': result.pages_visited,
                    'elapsed_seconds': round(time.time() - started_at, 2),
                    'capture_mode': capture_mode,
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            _orange_warning('A captura automática não conseguiu ler este fornecedor. Use a compatibilidade universal abaixo para importar HTML/CSV/XLSX ou tabela copiada.')
            return
        if not isinstance(result.df, pd.DataFrame) or result.df.empty:
            error_message = 'A captura autenticada não encontrou dados na página preparada. Use a compatibilidade universal abaixo quando o fornecedor bloquear iframe, sessão, captcha ou robô.'
            _clear_site_df(operation, 'captura_autenticada_vazia')
            _set_capture_state(operation=operation, running=False, finished=False, error=error_message)
            _finish_progress(progress, text='Captura encerrada sem produtos encontrados.')
            add_audit_event(
                'authenticated_site_capture_empty',
                area='SITE',
                step='entrada',
                status='AVISO',
                details={
                    'operation': operation,
                    'pages_visited': result.pages_visited,
                    'elapsed_seconds': round(time.time() - started_at, 2),
                    'capture_mode': capture_mode,
                    'state_reused': getattr(result, 'state_reused', False),
                    'state_saved': getattr(result, 'state_saved', False),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
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
        add_audit_event(
            'authenticated_site_capture_saved_to_state',
            area='SITE',
            step='entrada',
            status='OK',
            details={
                'operation': operation,
                'rows': len(df_site),
                'columns': len(df_site.columns),
                'pages_visited': result.pages_visited,
                'elapsed_seconds': round(time.time() - started_at, 2),
                'capture_mode': capture_mode,
                'state_reused': getattr(result, 'state_reused', False),
                'state_saved': getattr(result, 'state_saved', False),
                'responsible_file': RESPONSIBLE_FILE,
                'engine': 'BLING_INSTANT_SCRAPER',
            },
        )
        _finish_progress(progress, text='Captura autenticada concluída.')
        st.rerun()
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _clear_site_df(operation, 'captura_autenticada_exception')
        _set_capture_state(operation=operation, running=False, finished=False, error=message)
        _finish_progress(progress, text='Captura encerrada com falha.')
        add_audit_event(
            'authenticated_site_capture_exception',
            area='SITE',
            step='entrada',
            status='ERRO',
            details={
                'operation': operation,
                'error': message,
                'error_type': exc.__class__.__name__,
                'elapsed_seconds': round(time.time() - started_at, 2),
                'capture_mode': capture_mode,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _orange_warning('A captura automática falhou e foi destravada. Use a compatibilidade universal abaixo se este fornecedor bloquear robôs ou iframe.')
    finally:
        if not completed and bool(st.session_state.get('site_capture_running')):
            _clear_site_df(operation, 'captura_interrompida')
            _set_capture_state(
                operation=operation,
                running=False,
                finished=False,
                error=st.session_state.get('site_capture_error') or 'Captura interrompida antes de finalizar.',
            )
            _finish_progress(progress, text='Captura interrompida.')


def _run_site_capture(
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    raw_urls = str(raw_urls or '').strip()
    if _guided_login_enabled(operation):
        _run_authenticated_site_capture(operation, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
        return
    if not raw_urls:
        _clear_site_df(operation, 'busca_publica_sem_links')
        st.warning('Informe pelo menos um link antes de iniciar a busca por site.')
        add_audit_event('site_capture_blocked_missing_urls', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    if operation == 'estoque' and not _has_columns(requested_columns):
        _clear_site_df(operation, 'busca_estoque_sem_modelo')
        st.error('Busca bloqueada: carregue o modelo de estoque para definir exatamente quais colunas serão preenchidas.')
        add_audit_event('site_capture_blocked_missing_stock_model', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return

    started_at = time.time()
    st.session_state['site_capture_started_at'] = started_at
    _set_capture_state(operation=operation, running=True, finished=False)
    add_audit_event(
        'site_capture_started',
        area='SITE',
        step='entrada',
        details={
            'operation': operation,
            'requested_columns_count': len(requested_columns or []),
            'has_cadastro_model': isinstance(df_modelo_cadastro, pd.DataFrame),
            'has_estoque_model': isinstance(df_modelo_estoque, pd.DataFrame),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando produtos no site...')
    status_box = st.empty()
    try:
        df_site = run_site_engine(
            operation=operation,
            pipeline=load_site_pipeline(),
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            all_products=True,
            max_pages=ALL_PAGES_LIMIT,
            max_products=ALL_PRODUCTS_LIMIT,
            progress_callback=make_site_progress_callback(progress_bar, status_box),
        )
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _clear_site_df(operation, 'busca_publica_exception')
        _set_capture_state(operation=operation, running=False, finished=False, error=message)
        _finish_progress(progress_bar, status_box, text='Busca encerrada com erro.')
        add_audit_event('site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        st.error('A busca por site não conseguiu finalizar. Baixe o log debug para conferir o erro técnico.')
        return

    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        _clear_site_df(operation, 'busca_publica_vazia')
        _set_capture_state(operation=operation, running=False, finished=False, error='A busca por site não encontrou produtos válidos.', rows=0, columns=0)
        _finish_progress(progress_bar, status_box, text='Busca encerrada sem produtos encontrados.')
        add_audit_event('site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        st.warning('A busca por site não encontrou produtos válidos. Confira os links ou use a compatibilidade universal quando o fornecedor bloquear robôs.')
        return
    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    _store_site_df(operation, df_site)
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = 'site'
    _set_capture_state(operation=operation, running=False, finished=True, rows=rows, columns=columns)
    add_audit_event('site_capture_saved_to_state', area='SITE', step='entrada', status='OK', details={'operation': operation, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
    _finish_progress(progress_bar, status_box, text='Busca por site concluída.')
    st.rerun()


def render_site_panel() -> None:
    operation = _current_site_operation()
    if operation == 'estoque':
        from bling_app_zero.ui.estoque_site_panel import render_estoque_site_panel
        render_estoque_site_panel()
        return

    config = config_for_site_operation(operation)
    login_mode = _guided_login_enabled(operation)
    title = 'Captura autenticada pelo navegador do fornecedor' if login_mode else 'Cole os links do fornecedor'
    text = 'Fornecedor com entrada autenticada: faça login no navegador do fornecedor e execute a captura.' if login_mode else 'A captura acontece aqui. Depois continue para a próxima etapa do Wizard.'
    st.markdown(
        f'<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">{title}</h2><p class="bling-flow-card-text">{text}</p></section>',
        unsafe_allow_html=True,
    )
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
        login_confirmed = _login_confirmed()
        if not login_confirmed:
            _orange_warning('A captura autenticada está bloqueada até confirmar que você está logado e vendo a página de produtos.')
        button_label = '🔐 Executar captura autenticada pelo navegador do fornecedor'
        button_disabled = running or not login_confirmed
    else:
        button_label = 'Buscar no site e gerar origem de cadastro'
        button_disabled = running or (operation == 'estoque' and not _has_columns(requested_columns))

    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        add_audit_event('site_capture_main_button_clicked', area='SITE', step='entrada', details={'operation': operation, 'guided_login_enabled': _guided_login_enabled(operation), 'capture_mode': _guided_capture_mode() if _guided_login_enabled(operation) else 'public', 'responsible_file': RESPONSIBLE_FILE})
        _run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)

    _render_universal_fallback(
        operation=operation,
        requested_columns=requested_columns,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo,
    )

    df_site_bruto = _get_site_df(operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_site_source_summary(df_site_bruto, operation, show_history=False)
