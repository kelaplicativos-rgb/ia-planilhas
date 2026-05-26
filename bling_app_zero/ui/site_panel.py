from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import show_contract
from bling_app_zero.ui.manual_table_import_panel import render_manual_table_import_panel
from bling_app_zero.ui.site_models import (
    choose_site_cadastro_model_df,
    choose_site_estoque_model_df,
    choose_site_model_df,
    render_optional_site_model_upload,
    requested_columns_for_site_capture,
)
from bling_app_zero.ui.site_panel_capture import run_site_capture
from bling_app_zero.ui.site_panel_state import (
    UNIVERSAL_OPERATION,
    clear_legacy_authenticated_state,
    clear_stuck_capture,
    current_site_operation,
    get_site_df,
    has_columns,
    has_urls,
    orange_warning,
    query_urls_default,
    recover_stale_capture_if_needed,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'
SCAN_TOTAL_MAX_PAGES = 1_000_000
SCAN_TOTAL_MAX_PRODUCTS = 1_000_000
SCAN_TOTAL_MAX_DEPTH = 5


def _render_site_models_inline(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(operation)
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, operation)
    requested_columns = requested_columns_for_site_capture(operation, df_modelo_cadastro, df_modelo_estoque)
    if requested_columns:
        with st.expander('Campos que serão buscados', expanded=False):
            show_contract(requested_columns)
    else:
        st.error('Modelo de destino ausente. Anexe o modelo no início para definir quais campos serão buscados no site.')
    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input(operation: str) -> str:
    return st.text_area(
        'Links do fornecedor',
        value=query_urls_default(),
        height=120,
        key=f'urls_site_{operation}',
        placeholder='https://site.com.br\nhttps://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole a página inicial, categorias ou produtos. O sistema vai escanear o site inteiro atrás de produtos.',
    )


def _scan_total_options() -> dict[str, int | bool]:
    """SCAN TOTAL UI: sem modo teste e sem limite baixo manual."""
    return {
        'enabled': True,
        'max_pages': SCAN_TOTAL_MAX_PAGES,
        'max_products': SCAN_TOTAL_MAX_PRODUCTS,
        'max_depth': SCAN_TOTAL_MAX_DEPTH,
        'scan_total_ui': True,
    }


def _render_scan_total_notice() -> None:
    st.markdown(
        '<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">'
        '🚀 <b>SCAN TOTAL UI ativo:</b> o sistema não usa modo teste. Ao clicar no botão, ele procura produtos no site inteiro e prepara a origem conforme o modelo anexado.'
        '</div>',
        unsafe_allow_html=True,
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
        orange_warning('Use se o fornecedor bloquear robô, login, CAPTCHA, Cloudflare ou firewall. Você pode colar HTML, tabela, CSV ou XLSX.')
        render_manual_table_import_panel(
            operation=operation,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )


def render_site_panel() -> None:
    clear_legacy_authenticated_state()
    operation = current_site_operation()
    if operation not in {'cadastro', UNIVERSAL_OPERATION}:
        operation = UNIVERSAL_OPERATION

    recovered = recover_stale_capture_if_needed(operation)
    if recovered:
        orange_warning('A captura anterior ficou travada e foi destravada automaticamente. Revise os links e execute novamente.')

    df_site_bruto = get_site_df(operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        add_audit_event(
            'site_panel_compacted_after_origin_ready',
            area='SITE',
            step='entrada',
            status='OK',
            details={'operation': operation, 'rows': len(df_site_bruto), 'columns': len(df_site_bruto.columns), 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    st.markdown(
        '<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">SCAN TOTAL UI · Escanear site inteiro</h2></section>',
        unsafe_allow_html=True,
    )

    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input(operation)
    deep_options = _scan_total_options()
    _render_scan_total_notice()

    running = bool(st.session_state.get('site_capture_running'))
    has_urls_value = has_urls(raw_urls)
    if running:
        orange_warning('SCAN TOTAL em andamento. Aguarde a origem aparecer.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key=f'limpar_captura_travada_{operation}'):
            clear_stuck_capture(operation)
            st.rerun()

    error = str(st.session_state.get('site_capture_error') or '').strip()
    if error:
        st.error(f'Última captura falhou: {error}')

    button_label = '🚀 Escanear site inteiro agora'
    button_disabled = running or not has_urls_value or (operation in {UNIVERSAL_OPERATION} and not has_columns(requested_columns))

    if not has_urls_value:
        orange_warning('Cole pelo menos um link para liberar o SCAN TOTAL.')

    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        add_audit_event(
            'site_capture_main_button_clicked',
            area='SITE',
            step='entrada',
            details={
                'operation': operation,
                'capture_mode': 'scan_total_ui',
                'max_pages': SCAN_TOTAL_MAX_PAGES,
                'max_products': SCAN_TOTAL_MAX_PRODUCTS,
                'max_depth': SCAN_TOTAL_MAX_DEPTH,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, deep_options=deep_options)

    _render_universal_fallback(
        operation=operation,
        requested_columns=requested_columns,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo,
    )


__all__ = ['render_site_panel']
