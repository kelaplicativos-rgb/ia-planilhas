from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.flows.site_operation_router import config_for_site_operation
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
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'


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
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole um ou mais links públicos.',
    )


def _render_deep_capture_options(operation: str) -> dict[str, int | bool]:
    with st.expander('🌐 Captura profunda controlada do fornecedor', expanded=False):
        st.caption('Opcional. Use quando colar a página inicial ou uma categoria e quiser que o sistema procure mais links de produtos no mesmo domínio. Se desligado, o fluxo antigo continua igual.')
        enabled = st.checkbox(
            'Ativar captura profunda controlada',
            value=False,
            key=f'site_deep_capture_enabled_{operation}',
            help='Não baixa arquivos inúteis do site. Apenas varre páginas do mesmo domínio e transforma produtos encontrados em links para o motor atual.',
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            max_pages = st.number_input('Limite de páginas', min_value=20, max_value=5000, value=250, step=50, key=f'site_deep_capture_pages_{operation}')
        with col2:
            max_products = st.number_input('Limite de produtos', min_value=20, max_value=10000, value=500, step=50, key=f'site_deep_capture_products_{operation}')
        with col3:
            max_depth = st.number_input('Profundidade', min_value=0, max_value=5, value=2, step=1, key=f'site_deep_capture_depth_{operation}')
        st.caption('Recomendado: profundidade 1 ou 2. Profundidade alta pode demorar em sites grandes.')
    return {
        'enabled': bool(enabled),
        'max_pages': int(max_pages),
        'max_products': int(max_products),
        'max_depth': int(max_depth),
    }


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

    config = config_for_site_operation(operation)
    st.markdown(
        '<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">Entrada por site</div><h2 class="bling-flow-card-title">Cole os links do fornecedor</h2></section>',
        unsafe_allow_html=True,
    )

    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input(operation)
    deep_options = _render_deep_capture_options(operation)

    running = bool(st.session_state.get('site_capture_running'))
    has_urls_value = has_urls(raw_urls)
    if running:
        orange_warning('Captura por site em andamento. Aguarde a origem aparecer.')
        if st.button('🧹 Limpar captura travada e tentar novamente', use_container_width=True, key=f'limpar_captura_travada_{operation}'):
            clear_stuck_capture(operation)
            st.rerun()

    error = str(st.session_state.get('site_capture_error') or '').strip()
    if error:
        st.error(f'Última captura falhou: {error}')

    button_label = config.button_label
    if bool(deep_options.get('enabled')):
        button_label = '🌐 Buscar no site com captura profunda controlada'
    button_disabled = running or not has_urls_value or (operation in {UNIVERSAL_OPERATION} and not has_columns(requested_columns))

    if not has_urls_value:
        orange_warning('Cole pelo menos um link para liberar a busca.')

    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        add_audit_event('site_capture_main_button_clicked', area='SITE', step='entrada', details={'operation': operation, 'capture_mode': 'deep' if bool(deep_options.get('enabled')) else 'public', 'responsible_file': RESPONSIBLE_FILE})
        run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, deep_options=deep_options)

    _render_universal_fallback(
        operation=operation,
        requested_columns=requested_columns,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo,
    )


__all__ = ['render_site_panel']
