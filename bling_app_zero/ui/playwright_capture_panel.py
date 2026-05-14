from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.browser_capture.playwright_capture import (
    BrowserCaptureConfig,
    capture_html_with_saved_session,
    has_saved_session,
    is_playwright_available,
    session_debug,
)
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.manual_table_import_panel import _html_to_table, _store_manual_source

RESPONSIBLE_FILE = 'bling_app_zero/ui/playwright_capture_panel.py'
DEFAULT_URL = 'https://app.obaobamix.com.br/admin/products'


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _progress_callback(payload: dict) -> None:
    st.session_state['playwright_capture_last_progress'] = payload


def _render_progress() -> None:
    payload = st.session_state.get('playwright_capture_last_progress')
    if isinstance(payload, dict) and payload:
        message = str(payload.get('message') or payload.get('stage') or 'Processando...')
        st.caption(message)


def _config_from_ui(operation: str) -> BrowserCaptureConfig:
    supplier_url = st.text_input(
        'URL da tela de produtos do fornecedor',
        value=str(st.session_state.get('playwright_supplier_url') or DEFAULT_URL),
        key='playwright_supplier_url',
    )
    supplier_key = st.text_input(
        'Identificador da sessão',
        value=str(st.session_state.get('playwright_supplier_key') or 'obaobamix'),
        key='playwright_supplier_key',
        help='Usado para salvar/reutilizar a sessão desse fornecedor.',
    )
    max_pages = st.number_input('Máximo de páginas para tentar capturar', min_value=1, max_value=500, value=80, step=1, key='playwright_max_pages')
    wait_ms = st.number_input('Espera entre cliques/carregamentos (ms)', min_value=500, max_value=10000, value=1800, step=100, key='playwright_wait_ms')
    headless = st.checkbox(
        'Capturar em modo invisível/headless usando sessão salva',
        value=True,
        key='playwright_headless',
        help='Depois que a sessão já estiver salva, o sistema tenta capturar sem abrir janela gráfica.',
    )
    return BrowserCaptureConfig(
        supplier_url=supplier_url.strip(),
        supplier_key=supplier_key.strip() or operation,
        state_dir=Path('.bling_browser_state'),
        headless=bool(headless),
        max_pages=int(max_pages),
        wait_after_action_ms=int(wait_ms),
    )


def render_playwright_capture_panel(
    *,
    operation: str,
    requested_columns: list[str] | None = None,
    df_modelo_cadastro: pd.DataFrame | None = None,
    df_modelo_estoque: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> None:
    operation = 'estoque' if str(operation).lower() == 'estoque' else 'cadastro'
    st.markdown('###### BLINGPLAYWRIGHT · navegador de captura HTML')
    st.caption('Módulo isolado para tentar reutilizar uma sessão salva e capturar HTML de fornecedor com login.')

    available, error = is_playwright_available()
    if not available:
        _orange_warning(f'Playwright não está disponível neste ambiente: {error}')
        st.caption('O requirements.txt já possui playwright, mas o ambiente também precisa dos navegadores instalados com `playwright install chromium`.')
        return

    config = _config_from_ui(operation)
    debug = session_debug(config)
    if debug.get('has_saved_session'):
        st.success('Sessão salva encontrada para este fornecedor.')
    else:
        _orange_warning('Sessão salva ainda não encontrada. Primeiro faça login manual em ambiente compatível e salve a sessão.')

    with st.expander('Diagnóstico da sessão', expanded=False):
        st.json(debug)

    st.markdown('**Como salvar a sessão manualmente**')
    st.code(
        f'python -m bling_app_zero.browser_capture.runner login --url "{config.supplier_url}" --key "{config.supplier_key}"',
        language='bash',
    )
    st.caption('Esse comando deve ser rodado em máquina/servidor com navegador gráfico. Ele abre o Chromium, você faz login e pressiona ENTER no terminal para salvar a sessão.')

    can_capture = has_saved_session(config)
    if st.button('🧲 Capturar HTML usando sessão salva', use_container_width=True, disabled=not can_capture, key=f'playwright_capture_{operation}'):
        st.session_state['playwright_capture_last_progress'] = {}
        with st.spinner('Capturando HTML com Playwright...'):
            result = capture_html_with_saved_session(config, progress_callback=_progress_callback)
        _render_progress()
        if not result.ok:
            for warning in result.warnings:
                _orange_warning(warning)
            for err in result.errors:
                st.error(err)
            add_audit_event('playwright_capture_failed', area='SITE', status='ERRO', details={'operation': operation, 'errors': result.errors, 'responsible_file': RESPONSIBLE_FILE})
            return

        for warning in result.warnings:
            _orange_warning(warning)
        st.success(f'HTML capturado com {result.pages_captured} página(s)/bloco(s).')
        st.caption(f'Arquivo HTML: {result.file_path}')
        df = _html_to_table(result.html)
        if isinstance(df, pd.DataFrame) and not df.empty:
            _store_manual_source(
                df,
                operation=operation,
                raw_label=f'playwright:{result.file_path}',
                requested_columns=requested_columns,
                df_modelo_cadastro=df_modelo_cadastro,
                df_modelo_estoque=df_modelo_estoque,
                df_modelo=df_modelo,
            )
            add_audit_event('playwright_capture_imported', area='SITE', status='OK', details={'operation': operation, 'rows': len(df), 'columns': len(df.columns), 'pages': result.pages_captured, 'responsible_file': RESPONSIBLE_FILE})
        else:
            _orange_warning('Capturei o HTML, mas ainda não consegui transformar em tabela de produtos. Envie o HTML salvo pelo painel de compatibilidade universal para análise manual.')


__all__ = ['render_playwright_capture_panel']
