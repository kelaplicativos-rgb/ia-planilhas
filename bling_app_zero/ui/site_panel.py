from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.constants import (
    FLOW_CAPTURE_MAX_DEPTH,
    FLOW_CAPTURE_MAX_PAGES,
    FLOW_CAPTURE_MAX_PRODUCTS,
    SAFE_CAPTURE_MAX_DEPTH,
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
)
from bling_app_zero.features_runtime.router import active_contract, feature_needs_model
from bling_app_zero.ui.home_shared import show_contract
from bling_app_zero.ui.home_wizard_constants import STEP_DOWNLOAD, STEP_ENTRADA, STEP_MAPEAMENTO
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
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
from bling_app_zero.ui.site_progress import render_site_progress_history

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel.py'
SCAN_TOTAL_MAX_PAGES = SAFE_CAPTURE_MAX_PAGES
SCAN_TOTAL_MAX_PRODUCTS = SAFE_CAPTURE_MAX_PRODUCTS
SCAN_TOTAL_MAX_DEPTH = SAFE_CAPTURE_MAX_DEPTH
STOCK_BALANCE_MAX_PAGES = FLOW_CAPTURE_MAX_PAGES
STOCK_BALANCE_MAX_PRODUCTS = FLOW_CAPTURE_MAX_PRODUCTS
STOCK_BALANCE_MAX_DEPTH = FLOW_CAPTURE_MAX_DEPTH
SUPPORTED_SITE_OPERATIONS = {'cadastro', 'estoque', 'atualizacao_preco', UNIVERSAL_OPERATION}


def _columns_from_contract() -> list[str]:
    contract = active_contract()
    columns = list(dict.fromkeys([*contract.required_columns, *contract.optional_columns]))
    return [str(column).strip() for column in columns if str(column).strip()]


def _site_operation() -> str:
    contract = active_contract()
    if contract.is_api and contract.operation in SUPPORTED_SITE_OPERATIONS:
        return contract.operation
    operation = current_site_operation()
    if operation in SUPPORTED_SITE_OPERATIONS:
        return operation
    return UNIVERSAL_OPERATION


def _is_stock_api_balance_mode(operation: str) -> bool:
    contract = active_contract()
    return bool(contract.is_api and contract.operation == 'estoque' and operation == 'estoque')


def _next_step_after_site_capture() -> str:
    contract = active_contract()
    if contract.is_api:
        return STEP_DOWNLOAD
    return STEP_MAPEAMENTO


def _next_step_label() -> str:
    return 'Enviar para o Bling' if active_contract().is_api else 'Mapeamento'


def _render_site_models_inline(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    if not feature_needs_model():
        requested_columns = _columns_from_contract()
        if requested_columns:
            title = 'Campos de saldo que serão buscados' if _is_stock_api_balance_mode(operation) else 'Campos que serão buscados'
            with st.expander(title, expanded=False):
                show_contract(requested_columns)
        else:
            st.caption('Modo API direta: o sistema usará os campos mínimos do contrato ativo do Bling.')
        return None, None, None, None, requested_columns

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
    if _is_stock_api_balance_mode(operation):
        return st.text_area(
            'Link inicial, categoria ou produtos para buscar saldo',
            value=query_urls_default(),
            height=120,
            key=f'urls_site_{operation}',
            placeholder='https://site.com.br\nhttps://site.com.br/categoria\nhttps://site.com.br/produto-1',
            help='Cole a home, categoria ou links de produtos. O sistema varre em lote seguro para evitar queda da sessão no celular.',
        )

    return st.text_area(
        'Links para buscar produtos',
        value=query_urls_default(),
        height=120,
        key=f'urls_site_{operation}',
        placeholder='https://site.com.br\nhttps://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole página inicial, categorias ou produtos. O sistema vai procurar produtos e montar os dados importados.',
    )


def _scan_total_options(operation: str) -> dict[str, int | bool]:
    if _is_stock_api_balance_mode(operation):
        return {
            'enabled': True,
            'max_pages': STOCK_BALANCE_MAX_PAGES,
            'max_products': STOCK_BALANCE_MAX_PRODUCTS,
            'max_depth': STOCK_BALANCE_MAX_DEPTH,
            'scan_total_ui': True,
            'stock_balance_only': True,
            'stock_full_site_scan': True,
            'budget_seconds': 24,
        }
    return {
        'enabled': True,
        'max_pages': SCAN_TOTAL_MAX_PAGES,
        'max_products': SCAN_TOTAL_MAX_PRODUCTS,
        'max_depth': SCAN_TOTAL_MAX_DEPTH,
        'scan_total_ui': True,
        'stock_balance_only': False,
        'stock_full_site_scan': False,
        'budget_seconds': 24,
    }


def _render_scan_total_notice(operation: str) -> None:
    if _is_stock_api_balance_mode(operation):
        st.markdown(
            '<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">'
            '📦 <b>Modo saldo de estoque completo:</b> o sistema varre os produtos encontrados em lote seguro, prepara ID/código/GTIN, quantidade/saldo e depósito, e evita processamento gigante em uma única sessão do celular.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">'
        '🚀 <b>Busca completa ativa:</b> ao clicar no botão, o sistema procura produtos no site e prepara os dados importados conforme o contrato ativo.'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_running_state(operation: str) -> None:
    if _is_stock_api_balance_mode(operation):
        orange_warning('Busca de saldos em andamento em modo seguro. O sistema está localizando produtos do site sem sobrecarregar a sessão do celular.')
    else:
        orange_warning('Busca por site em andamento. Acompanhe a barra de progresso e aguarde os dados importados aparecerem.')
    render_site_progress_history()
    if st.button('🧹 Limpar busca travada e tentar novamente', use_container_width=True, key=f'limpar_captura_travada_{operation}'):
        clear_stuck_capture(operation)
        safe_rerun('site_capture_stuck_cleared', target_step=STEP_ENTRADA)


def _render_last_error(error: str, operation: str) -> None:
    if not error:
        return
    if _is_stock_api_balance_mode(operation):
        st.error('A última busca completa de saldo de estoque não conseguiu finalizar.')
        st.caption('Confira o link inicial/categoria ou use Site protegido para colar tabela com Código/ID produto e Quantidade/Saldo.')
    else:
        st.error('A última busca por site não conseguiu finalizar.')
        st.caption('Confira os links, tente novamente ou use a opção de site protegido para colar HTML, tabela, CSV ou XLSX.')
    with st.expander('Detalhe da falha', expanded=False):
        st.code(error)


def _clear_smartscan_manual_flags() -> None:
    for key in (
        'blingsmartscan_manual_continue_required',
        'blingsmartscan_ready_to_continue',
        'blingsmartscan_continue_target_step',
        'blingsmartscan_finished_operation',
        'blingsmartscan_finished_rows',
        'blingsmartscan_finished_columns',
    ):
        st.session_state.pop(key, None)


def _render_ready_state(operation: str, df_site_bruto: pd.DataFrame, stock_balance_only: bool) -> None:
    rows = len(df_site_bruto)
    columns = len(df_site_bruto.columns)
    title = 'Saldos capturados e salvos' if stock_balance_only else 'Produtos capturados e salvos'
    next_step = _next_step_after_site_capture()
    next_label = _next_step_label()
    st.success(f'{title}: {rows} produto(s), {columns} coluna(s).')
    notice = st.session_state.get(f'blingsmartscan_notice_{operation}') or st.session_state.get('blingsmartscan_last_notice') or {}
    if isinstance(notice, dict) and notice:
        with st.expander('Resumo do BLINGSMARTSCAN', expanded=False):
            if notice.get('platform'):
                st.caption(f"Plataforma provável: {notice.get('platform')} ({notice.get('confidence', 0)}%).")
            if notice.get('score') is not None:
                st.metric('Qualidade da captura', f"{notice.get('score')}/100")
            for warning in list(notice.get('warnings') or [])[:5]:
                st.warning(str(warning))
    st.caption(f'O resultado já está salvo em Origem dos dados. Toque abaixo para seguir para {next_label}.')
    if st.button(f'Continuar para {next_label}', use_container_width=True, key=f'continuar_pos_smartscan_{operation}'):
        _clear_smartscan_manual_flags()
        add_audit_event('site_panel_manual_continue_clicked', area='SITE', step=next_step, status='OK', details={'operation': operation, 'rows': rows, 'columns': columns, 'stock_balance_only': stock_balance_only, 'target_step': next_step, 'responsible_file': RESPONSIBLE_FILE})
        safe_rerun('site_capture_manual_continue', target_step=next_step)


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
        if _is_stock_api_balance_mode(operation):
            orange_warning('Use se os saldos estiverem em tela protegida. Cole HTML, tabela, CSV ou XLSX contendo produto e saldo.')
        else:
            orange_warning('Use se o fornecedor bloquear a busca automática. Você pode colar HTML, tabela, CSV ou XLSX.')
        render_manual_table_import_panel(
            operation=operation,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )


def render_site_panel() -> None:
    clear_legacy_authenticated_state()
    operation = _site_operation()
    stock_balance_only = _is_stock_api_balance_mode(operation)

    recovered = recover_stale_capture_if_needed(operation)
    if recovered:
        if stock_balance_only:
            orange_warning('A busca anterior de saldo ficou travada e foi destravada automaticamente. Revise os links e execute novamente.')
        else:
            orange_warning('A busca anterior ficou travada e foi destravada automaticamente. Revise os links e execute novamente.')

    df_site_bruto = get_site_df(operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        add_audit_event(
            'site_panel_ready_after_origin_capture',
            area='SITE',
            step='entrada',
            status='OK',
            details={'operation': operation, 'rows': len(df_site_bruto), 'columns': len(df_site_bruto.columns), 'stock_balance_only': stock_balance_only, 'manual_continue': True, 'target_step': _next_step_after_site_capture(), 'responsible_file': RESPONSIBLE_FILE},
        )
        _render_ready_state(operation, df_site_bruto, stock_balance_only)
        return

    title = 'Buscar saldos de todos os produtos' if stock_balance_only else 'Buscar produtos no site'
    kicker = 'Estoque API' if stock_balance_only else 'Entrada por site'
    st.markdown(
        f'<section class="bling-flow-card bling-inline-card"><div class="bling-flow-card-kicker">{kicker}</div><h2 class="bling-flow-card-title">{title}</h2></section>',
        unsafe_allow_html=True,
    )

    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input(operation)
    deep_options = _scan_total_options(operation)
    _render_scan_total_notice(operation)

    running = bool(st.session_state.get('site_capture_running'))
    has_urls_value = has_urls(raw_urls)
    if running:
        _render_running_state(operation)

    error = str(st.session_state.get('site_capture_error') or '').strip()
    _render_last_error(error, operation)

    button_label = '🔎 Buscar saldos em modo seguro' if stock_balance_only else '🚀 Buscar produtos agora'
    needs_model = feature_needs_model()
    button_disabled = running or not has_urls_value or (needs_model and operation in {UNIVERSAL_OPERATION} and not has_columns(requested_columns))

    if not has_urls_value:
        orange_warning('Cole pelo menos um link para liberar a busca.')

    if needs_model and operation in {UNIVERSAL_OPERATION} and not has_columns(requested_columns):
        orange_warning('Modelo de destino necessário: envie o modelo para o sistema saber quais campos buscar.')

    if st.button(button_label, use_container_width=True, disabled=button_disabled, key=f'buscar_site_{operation}'):
        add_audit_event(
            'site_capture_main_button_clicked',
            area='SITE',
            step='entrada',
            details={
                'operation': operation,
                'feature_contract': active_contract().key,
                'capture_mode': 'stock_balance_safe_site_search' if stock_balance_only else 'full_site_search',
                'max_pages': int(deep_options.get('max_pages') or SCAN_TOTAL_MAX_PAGES),
                'max_products': int(deep_options.get('max_products') or SCAN_TOTAL_MAX_PRODUCTS),
                'max_depth': int(deep_options.get('max_depth') or 0),
                'stock_balance_only': stock_balance_only,
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
