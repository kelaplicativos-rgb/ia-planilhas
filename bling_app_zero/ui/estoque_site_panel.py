from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.manual_table_import_panel import render_manual_table_import_panel
from bling_app_zero.ui.site_models import choose_site_estoque_model_df, choose_site_model_df, render_optional_site_model_upload, requested_columns_for_site_capture
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
OPERATION = 'estoque'
STOCK_SITE_DF_KEY = 'df_site_bruto_estoque'
RESPONSIBLE_FILE = 'bling_app_zero/ui/estoque_site_panel.py'


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


def _set_stock_capture_state(*, running: bool, error: str = '') -> None:
    st.session_state['site_capture_running'] = running
    st.session_state['site_capture_error'] = error
    st.session_state['site_capture_operation'] = OPERATION
    st.session_state['site_capture_result_ready'] = False if error else st.session_state.get('site_capture_result_ready', False)


def _clear_stock_site_df(reason: str) -> None:
    removed: list[str] = []
    for key in (STOCK_SITE_DF_KEY, 'df_site_bruto'):
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    add_audit_event(
        'stock_site_stale_source_cleared',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={'operation': OPERATION, 'reason': reason, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
    )


def _clear_stuck_capture() -> None:
    _clear_stock_site_df('captura_travada_limpa_manualmente')
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
    st.session_state['site_capture_result_ready'] = bool(not clean_df.empty)
    st.session_state['site_capture_rows'] = int(len(clean_df))
    st.session_state['site_capture_columns'] = int(len(clean_df.columns))


def _render_stock_model_contract() -> tuple[pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(OPERATION)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, OPERATION)
    requested_columns = requested_columns_for_site_capture(OPERATION, df_modelo_cadastro=None, df_modelo_estoque=df_modelo_estoque)
    if requested_columns:
        with st.expander('Campos que serão buscados', expanded=False):
            show_contract(requested_columns)
        st.caption('A busca por site vai tentar preencher somente as colunas acima. O que não for encontrado fica vazio.')
    else:
        st.error('Carregue o modelo de destino desta atualização. A busca só será feita nas colunas desse modelo.')
    return df_modelo, requested_columns


def _render_urls_input() -> str:
    return st.text_area(
        'Links do fornecedor',
        value=_query_urls_default(),
        height=120,
        key='urls_site_estoque_independente',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole links de categoria, busca ou item individual.',
    )


def _render_universal_fallback(*, requested_columns: list[str] | None, df_modelo_estoque: pd.DataFrame | None) -> None:
    with st.expander('🔐 Site protegido, bloqueado ou com login', expanded=False):
        st.caption('Abra somente se a busca normal não funcionar ou se o fornecedor exigir login, CAPTCHA, Cloudflare, firewall ou tabela copiada.')
        _orange_warning('Compatibilidade universal: use quando o site bloquear robô, iframe, sessão, login, CAPTCHA ou Cloudflare. Você pode colar HTML, tabela copiada ou enviar HTML/XLSX/CSV já salvo.')
        render_manual_table_import_panel(
            operation=OPERATION,
            requested_columns=requested_columns,
            df_modelo_cadastro=None,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo_estoque,
        )


def _run_stock_site_capture(raw_urls: str, requested_columns: list[str] | None, df_modelo_estoque: pd.DataFrame | None) -> None:
    raw_urls = str(raw_urls or '').strip()
    if not raw_urls:
        _clear_stock_site_df('busca_publica_sem_links')
        st.warning('Informe pelo menos um link antes de iniciar a busca por site.')
        return
    if not _has_columns(requested_columns):
        _clear_stock_site_df('busca_sem_modelo')
        st.error('Busca bloqueada: o modelo de destino precisa definir exatamente quais colunas serão preenchidas.')
        return
    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando dados no site...')
    status_box = st.empty()
    try:
        df_site = run_site_engine(operation=OPERATION, pipeline=load_site_pipeline(), raw_urls=raw_urls, requested_columns=requested_columns, all_products=True, max_pages=ALL_PAGES_LIMIT, max_products=ALL_PRODUCTS_LIMIT, progress_callback=make_site_progress_callback(progress_bar, status_box))
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _clear_stock_site_df('busca_publica_exception')
        _set_stock_capture_state(running=False, error=message)
        _finish_progress(progress_bar, status_box, text='Busca encerrada com erro.')
        add_audit_event('stock_site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': OPERATION, 'error': message, 'error_type': exc.__class__.__name__, 'responsible_file': RESPONSIBLE_FILE})
        st.error('A busca por site não conseguiu finalizar. Baixe o diagnóstico para correção na sidebar.')
        return
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        _clear_stock_site_df('busca_publica_vazia')
        _set_stock_capture_state(running=False, error='A busca por site não encontrou dados válidos.')
        _finish_progress(progress_bar, status_box, text='Busca encerrada sem dados.')
        add_audit_event('stock_site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': OPERATION, 'responsible_file': RESPONSIBLE_FILE})
        st.warning('A busca por site não encontrou dados válidos. Confira os links ou use a compatibilidade universal.')
        return
    save_site_source(df_site=df_site, raw_urls=raw_urls, requested_columns=requested_columns, df_modelo_cadastro=None, df_modelo_estoque=df_modelo_estoque, df_modelo=df_modelo_estoque, operation=OPERATION)
    _store_stock_site_df(df_site)
    _set_stock_capture_state(running=False, error='')
    _finish_progress(progress_bar, status_box, text='Busca por site concluída.')
    st.rerun()


def render_estoque_site_panel() -> None:
    df_site_bruto = _get_stock_site_df()
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_site_source_summary(df_site_bruto, OPERATION, show_history=False)
        st.success('Dados capturados por site enviados para Dados de origem. Continue no mapeamento abaixo.')
        return

    st.markdown('<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">Cole os links do fornecedor</h2><p class="bling-flow-card-text">Este painel usa o modelo de destino escolhido e procura somente os campos pedidos nele.</p></section>', unsafe_allow_html=True)
    st.info('Entrada por site: o sistema busca dados do fornecedor para preencher o modelo escolhido no mapeamento.')
    df_modelo_estoque, requested_columns = _render_stock_model_contract()
    raw_urls = _render_urls_input()
    running = bool(st.session_state.get('site_capture_running'))
    if running:
        _orange_warning('Captura por site em andamento. Aguarde a origem aparecer antes de continuar.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key='limpar_captura_travada_estoque'):
            _clear_stuck_capture()
            st.rerun()
    button_label = 'Buscar no site e gerar origem'
    button_disabled = running or not _has_columns(requested_columns)
    if not _has_columns(requested_columns):
        st.caption('O botão será liberado quando o modelo de destino estiver carregado.')
    if st.button(button_label, use_container_width=True, disabled=button_disabled, key='buscar_site_estoque_independente'):
        add_audit_event('stock_site_capture_main_button_clicked', area='SITE', step='entrada', details={'operation': OPERATION, 'capture_mode': 'public', 'responsible_file': RESPONSIBLE_FILE})
        _run_stock_site_capture(raw_urls, requested_columns, df_modelo_estoque)
    _render_universal_fallback(requested_columns=requested_columns, df_modelo_estoque=df_modelo_estoque)


__all__ = ['render_estoque_site_panel']
