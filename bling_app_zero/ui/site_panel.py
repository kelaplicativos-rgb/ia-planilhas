from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.flows.site_operation_router import config_for_site_operation, run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.manual_table_import_panel import render_manual_table_import_panel
from bling_app_zero.ui.site_models import (
    choose_site_cadastro_model_df,
    choose_site_estoque_model_df,
    choose_site_model_df,
    render_optional_site_model_upload,
    requested_columns_for_site_capture,
)
from bling_app_zero.ui.site_outputs import save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'
LEGACY_AUTH_KEYS = (
    'guided_login_confirmed_logged_in',
    'guided_login_capture_config',
    'guided_login_capture_prompt',
    'guided_login_capture_last_prepared_at',
    'guided_login_security_resolved',
    'guided_login_products_page_ready',
    'guided_login_capture_mode',
    'guided_login_remote_snapshot_url',
    'guided_login_remote_snapshot_final_url',
    'guided_login_remote_snapshot_title',
    'guided_login_remote_snapshot_ok',
    'guided_login_remote_snapshot_png',
    'guided_login_remote_last_click_nonce',
    'guided_login_remote_desktop_ready',
    'guided_login_remote_desktop_url_ready',
)


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
    flow = str(_query_param('operacao') or '').strip().lower()
    if flow in {'cadastro', 'cadastro_site'}:
        return 'cadastro'
    if flow in {'estoque', 'estoque_site', 'stock', 'stock_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    return ''


def _site_df_key(operation: str) -> str:
    return f'df_site_bruto_{operation}'


def _store_site_df(operation: str, df_site: pd.DataFrame) -> None:
    st.session_state[_site_df_key(operation)] = df_site
    st.session_state['df_site_bruto'] = df_site
    other = 'estoque' if operation == 'cadastro' else 'cadastro'
    st.session_state.pop(_site_df_key(other), None)


def _clear_site_df(operation: str, reason: str) -> None:
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
        details={
            'operation': operation,
            'reason': reason,
            'removed_keys': removed,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _clear_legacy_authenticated_state() -> None:
    removed: list[str] = []
    for key in LEGACY_AUTH_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    for key in list(st.session_state.keys()):
        if str(key).startswith('site_guided_login_enabled_'):
            st.session_state.pop(key, None)
            removed.append(str(key))
    if removed:
        add_audit_event(
            'legacy_authenticated_site_state_cleared',
            area='SITE',
            step='entrada',
            status='OK',
            details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
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


def _has_urls(raw_urls: str) -> bool:
    return bool(str(raw_urls or '').strip())


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _finish_progress(progress, status_box=None, text: str = 'Captura encerrada.') -> None:
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


def _render_site_models_inline(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(operation)
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, operation)
    requested_columns = requested_columns_for_site_capture(operation, df_modelo_cadastro, df_modelo_estoque)
    if requested_columns:
        with st.expander('Campos que serão buscados', expanded=False):
            show_contract(requested_columns)
    elif operation == 'estoque':
        st.error('Modelo de destino ausente.')
    else:
        st.warning('Modelo de destino ausente. A captura usará campos principais.')
    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input(operation: str) -> str:
    return st.text_area(
        'Links do fornecedor',
        value=_query_urls_default(),
        height=120,
        key=f'urls_site_{operation}',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole um ou mais links públicos.',
    )


def _set_capture_state(*, operation: str, running: bool, finished: bool, error: str = '', rows: int = 0, columns: int = 0) -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_finished'] = finished
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = operation
    st.session_state['site_capture_result_ready'] = bool(finished and not error and rows > 0)
    st.session_state['site_capture_rows'] = int(rows or 0)
    st.session_state['site_capture_columns'] = int(columns or 0)


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


def _render_universal_fallback(
    *,
    operation: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    expanded = bool(st.session_state.get('site_capture_error'))
    with st.expander('🔐 Site protegido ou com login', expanded=expanded):
        _orange_warning('Use se o fornecedor bloquear robô, login, CAPTCHA, Cloudflare ou firewall. Você pode colar HTML, tabela, CSV ou XLSX.')
        render_manual_table_import_panel(
            operation=operation,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )


def _run_site_capture(
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    raw_urls = str(raw_urls or '').strip()
    if not raw_urls:
        _clear_site_df(operation, 'busca_publica_sem_links')
        st.warning('Cole pelo menos um link para buscar.')
        add_audit_event('site_capture_blocked_missing_urls', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    if operation == 'estoque' and not _has_columns(requested_columns):
        _clear_site_df(operation, 'busca_sem_modelo_destino')
        st.error('Busca bloqueada: modelo de destino ausente.')
        add_audit_event('site_capture_blocked_missing_model', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
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
    progress_bar = st.progress(0, text='Buscando dados no site...')
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
        st.error('A busca por site não conseguiu finalizar. Baixe o log debug.')
        return

    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        _clear_site_df(operation, 'busca_publica_vazia')
        _set_capture_state(operation=operation, running=False, finished=False, error='A busca por site não encontrou dados válidos.', rows=0, columns=0)
        _finish_progress(progress_bar, status_box, text='Busca encerrada sem dados encontrados.')
        add_audit_event('site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        st.warning('Nenhum dado encontrado. Confira os links ou use Site protegido.')
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
    _clear_legacy_authenticated_state()
    operation = _current_site_operation()
    if operation not in {'cadastro', 'estoque'}:
        st.warning('Escolha primeiro o objetivo do mapeamento.')
        add_audit_event('site_panel_blocked_missing_operation', area='SITE', step='entrada', status='BLOQUEADO', details={'responsible_file': RESPONSIBLE_FILE})
        return
    if operation == 'estoque':
        from bling_app_zero.ui.estoque_site_panel import render_estoque_site_panel
        render_estoque_site_panel()
        return

    df_site_bruto = _get_site_df(operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        add_audit_event(
            'site_panel_compacted_after_origin_ready',
            area='SITE',
            step='entrada',
            status='OK',
            details={'operation': operation, 'rows': len(df_site_bruto), 'columns': len(df_site_bruto.columns), 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    config = config_for_site_operation(operation)
    st.markdown(
        '<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">Cole os links do fornecedor</h2></section>',
        unsafe_allow_html=True,
    )

    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input(operation)

    running = bool(st.session_state.get('site_capture_running'))
    has_urls = _has_urls(raw_urls)
    if running:
        _orange_warning('Captura por site em andamento. Aguarde a origem aparecer.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key=f'limpar_captura_travada_{operation}'):
            _clear_stuck_capture(operation)
            st.rerun()

    error = str(st.session_state.get('site_capture_error') or '').strip()
    if error:
        st.error(f'Última captura falhou: {error}')

    button_label = config.button_label
    button_disabled = running or not has_urls or (operation == 'estoque' and not _has_columns(requested_columns))

    if not has_urls:
        _orange_warning('Cole pelo menos um link para liberar a busca.')

    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        add_audit_event('site_capture_main_button_clicked', area='SITE', step='entrada', details={'operation': operation, 'capture_mode': 'public', 'responsible_file': RESPONSIBLE_FILE})
        _run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)

    _render_universal_fallback(
        operation=operation,
        requested_columns=requested_columns,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo,
    )


__all__ = ['render_site_panel']
