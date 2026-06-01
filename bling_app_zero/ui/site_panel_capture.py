from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.deep_site_capture import discover_deep_product_urls
from bling_app_zero.features_runtime.router import active_contract, feature_needs_model
from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline
from bling_app_zero.ui.home_wizard_constants import STEP_MAPEAMENTO
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.site_outputs import save_site_source
from bling_app_zero.ui.site_panel_state import (
    UNIVERSAL_OPERATION,
    clear_site_df,
    has_columns,
    set_capture_state,
    store_site_df,
)
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
STOCK_BALANCE_PAGES_LIMIT = 1
STOCK_BALANCE_PRODUCTS_LIMIT = 5_000
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_capture.py'


def finish_progress(progress, status_box=None, text: str = 'Captura encerrada.') -> None:
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


def _is_stock_balance_only(operation: str, deep_options: dict[str, int | bool] | None) -> bool:
    contract = active_contract()
    options = deep_options or {}
    return bool(options.get('stock_balance_only') or (contract.is_api and contract.operation == 'estoque' and operation == 'estoque'))


def prepare_raw_urls_for_capture(
    *,
    operation: str,
    raw_urls: str,
    deep_options: dict[str, int | bool] | None,
    progress_bar,
    status_box,
) -> tuple[str, dict[str, object]]:
    options = deep_options or {}
    if _is_stock_balance_only(operation, options):
        return raw_urls, {
            'deep_capture_enabled': False,
            'stock_balance_only': True,
            'scan_mode': 'stock_balance_product_links_only',
            'reason': 'Operação de estoque via API deve buscar somente saldos dos produtos informados, sem varredura profunda.',
        }

    if not bool(options.get('enabled')):
        return raw_urls, {'deep_capture_enabled': False, 'scan_mode': 'full_public_scan'}

    callback = make_site_progress_callback(progress_bar, status_box)
    result = discover_deep_product_urls(
        raw_urls,
        max_pages=int(options.get('max_pages') or 250),
        max_products=int(options.get('max_products') or 500),
        max_depth=int(options.get('max_depth') or 2),
        progress_callback=callback,
    )

    if not result.product_urls:
        return raw_urls, {
            'deep_capture_enabled': True,
            'deep_capture_found_products': 0,
            'deep_capture_visited_pages': result.visited_pages,
            'scan_mode': 'full_deep_scan_no_links_found',
        }

    st.session_state[f'site_deep_capture_urls_{operation}'] = result.raw_urls
    st.session_state[f'site_deep_capture_found_{operation}'] = len(result.product_urls)
    return result.raw_urls, {
        'deep_capture_enabled': True,
        'deep_capture_found_products': len(result.product_urls),
        'deep_capture_visited_pages': result.visited_pages,
        'deep_capture_scanned_pages': result.scanned_pages,
        'deep_capture_ignored_external_links': result.ignored_external_links,
        'deep_capture_max_depth': result.max_depth,
        'scan_mode': 'full_deep_scan',
    }


def capture_limits_for_operation(operation: str, deep_options: dict[str, int | bool] | None) -> tuple[int, int, bool]:
    """Define limites por tipo de busca.

    Cadastro/site continua com busca completa. Estoque via API usa modo enxuto para
    saldo por produto, evitando crawler profundo, timeout e mistura de dados de cadastro.
    """
    options = deep_options or {}
    if _is_stock_balance_only(operation, options):
        return (
            max(1, int(options.get('max_pages') or STOCK_BALANCE_PAGES_LIMIT)),
            max(1, int(options.get('max_products') or STOCK_BALANCE_PRODUCTS_LIMIT)),
            False,
        )
    if bool(options.get('enabled')):
        return (
            max(int(options.get('max_pages') or 0), ALL_PAGES_LIMIT),
            max(int(options.get('max_products') or 0), ALL_PRODUCTS_LIMIT),
            True,
        )
    return ALL_PAGES_LIMIT, ALL_PRODUCTS_LIMIT, True


def _missing_model_blocked(operation: str, requested_columns: list[str] | None) -> bool:
    return bool(feature_needs_model() and operation in {UNIVERSAL_OPERATION} and not has_columns(requested_columns))


def _persist_operation_state(operation: str) -> None:
    contract = active_contract()
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = 'site'
    st.session_state['home_slim_flow_operation'] = contract.operation
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['active_feature_contract_key'] = contract.key
    st.session_state['active_feature_operation'] = contract.operation
    st.session_state['active_feature_mode'] = contract.mode


def run_site_capture(
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    deep_options: dict[str, int | bool] | None = None,
) -> None:
    raw_urls = str(raw_urls or '').strip()
    if not raw_urls:
        clear_site_df(operation, 'busca_publica_sem_links')
        st.warning('Cole pelo menos um link para buscar.')
        add_audit_event('site_capture_blocked_missing_urls', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    if _missing_model_blocked(operation, requested_columns):
        clear_site_df(operation, 'busca_sem_modelo_destino')
        st.error('Busca bloqueada: modelo de destino ausente.')
        add_audit_event('site_capture_blocked_missing_model', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'feature_contract': active_contract().key, 'responsible_file': RESPONSIBLE_FILE})
        return

    started_at = time.time()
    stock_balance_only = _is_stock_balance_only(operation, deep_options)
    st.session_state['site_capture_started_at'] = started_at
    set_capture_state(operation=operation, running=True, finished=False)
    max_pages, max_products, all_products = capture_limits_for_operation(operation, deep_options)
    add_audit_event(
        'site_capture_started',
        area='SITE',
        step='entrada',
        details={
            'operation': operation,
            'feature_contract': active_contract().key,
            'requested_columns_count': len(requested_columns or []),
            'has_cadastro_model': isinstance(df_modelo_cadastro, pd.DataFrame),
            'has_estoque_model': isinstance(df_modelo_estoque, pd.DataFrame),
            'deep_capture_requested': bool((deep_options or {}).get('enabled')),
            'stock_balance_only': stock_balance_only,
            'all_products': bool(all_products),
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'scan_goal': 'saldo_estoque_produtos_informados' if stock_balance_only else 'site_completo_sem_amostra',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    reset_site_progress()
    progress_text = 'Buscando saldos dos produtos informados...' if stock_balance_only else 'Escaneando o site completo atrás de produtos...'
    progress_bar = st.progress(0, text=progress_text)
    status_box = st.empty()
    try:
        prepared_urls, deep_details = prepare_raw_urls_for_capture(
            operation=operation,
            raw_urls=raw_urls,
            deep_options=deep_options,
            progress_bar=progress_bar,
            status_box=status_box,
        )
        df_site = run_site_engine(
            operation=operation,
            pipeline=load_site_pipeline(),
            raw_urls=prepared_urls,
            requested_columns=requested_columns,
            all_products=all_products,
            max_pages=max_pages,
            max_products=max_products,
            progress_callback=make_site_progress_callback(progress_bar, status_box),
        )
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        clear_site_df(operation, 'busca_publica_exception')
        set_capture_state(operation=operation, running=False, finished=False, error=message)
        finish_progress(progress_bar, status_box, text='Busca encerrada com erro.')
        add_audit_event('site_capture_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        if stock_balance_only:
            st.error('A busca de saldo dos produtos não conseguiu finalizar. Baixe o log debug.')
        else:
            st.error('A busca por site não conseguiu finalizar. Baixe o log debug.')
        return

    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        clear_site_df(operation, 'busca_publica_vazia')
        empty_message = 'A busca de saldo não encontrou dados válidos.' if stock_balance_only else 'A busca por site não encontrou dados válidos.'
        set_capture_state(operation=operation, running=False, finished=False, error=empty_message, rows=0, columns=0)
        finish_progress(progress_bar, status_box, text='Busca encerrada sem dados encontrados.')
        add_audit_event('site_capture_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        if stock_balance_only:
            st.warning('Nenhum saldo encontrado. Confira os links de produto ou cole uma tabela com Código/ID e Quantidade.')
        else:
            st.warning('Nenhum dado encontrado. Confira os links ou use Site protegido.')
        return

    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    store_site_df(operation, df_site)
    _persist_operation_state(operation)
    set_capture_state(operation=operation, running=False, finished=True, rows=rows, columns=columns)
    details = {
        'operation': operation,
        'feature_contract': active_contract().key,
        'rows': rows,
        'columns': columns,
        'elapsed_seconds': round(time.time() - started_at, 2),
        'max_pages': int(max_pages),
        'max_products': int(max_products),
        'all_products': bool(all_products),
        'stock_balance_only': stock_balance_only,
        'scan_goal': 'saldo_estoque_produtos_informados' if stock_balance_only else 'site_completo_sem_amostra',
        'responsible_file': RESPONSIBLE_FILE,
    }
    details.update(deep_details)
    add_audit_event('site_capture_saved_to_state', area='SITE', step='entrada', status='OK', details=details)
    finish_progress(progress_bar, status_box, text='Busca de saldos concluída.' if stock_balance_only else 'Busca por site concluída.')
    safe_rerun('site_capture_finished', target_step=STEP_MAPEAMENTO)


__all__ = ['capture_limits_for_operation', 'run_site_capture']