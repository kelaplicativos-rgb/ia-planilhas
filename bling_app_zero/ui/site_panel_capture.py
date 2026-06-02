from __future__ import annotations

import time
from dataclasses import asdict

import pandas as pd
import streamlit as st

from bling_app_zero.agents.site_capture_agent import run_bling_smartscan
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.constants import (
    DISCOVERY_BUDGET_SECONDS,
    FLOW_CAPTURE_MAX_DEPTH,
    FLOW_CAPTURE_MAX_PAGES,
    FLOW_CAPTURE_MAX_PRODUCTS,
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
)
from bling_app_zero.engines.fast_site_scraper.deep_site_capture import discover_deep_product_urls
from bling_app_zero.features_runtime.router import active_contract, feature_needs_model
from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline
from bling_app_zero.ui.home_wizard_constants import STEP_DOWNLOAD, STEP_MAPEAMENTO
from bling_app_zero.ui.site_outputs import save_site_source
from bling_app_zero.ui.site_panel_state import (
    UNIVERSAL_OPERATION,
    clear_site_df,
    has_columns,
    set_capture_state,
    store_site_df,
)
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = SAFE_CAPTURE_MAX_PAGES
ALL_PRODUCTS_LIMIT = SAFE_CAPTURE_MAX_PRODUCTS
STOCK_BALANCE_PAGES_LIMIT = FLOW_CAPTURE_MAX_PAGES
STOCK_BALANCE_PRODUCTS_LIMIT = FLOW_CAPTURE_MAX_PRODUCTS
STOCK_BALANCE_DEPTH_LIMIT = FLOW_CAPTURE_MAX_DEPTH
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_panel_capture.py'


def finish_progress(progress, status_box=None, text: str = 'Captura encerrada.') -> None:
    if progress is not None:
        try:
            progress.progress(100, text=text)
            time.sleep(0.10)
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


def _is_stock_full_site_scan(operation: str, deep_options: dict[str, int | bool] | None) -> bool:
    options = deep_options or {}
    return bool(_is_stock_balance_only(operation, options) and options.get('stock_full_site_scan', True))


def _next_step_after_capture() -> str:
    return STEP_DOWNLOAD if active_contract().is_api else STEP_MAPEAMENTO


def _next_step_label_after_capture() -> str:
    return 'Enviar para o Bling' if active_contract().is_api else 'Mapeamento'


def _orange_notice(message: str) -> None:
    st.warning(message)


def _smartscan_notice_payload(report, *, rows: int) -> dict[str, object]:
    try:
        quality = report.quality
        platform = report.platform
        return {
            'title': 'BLINGSMARTSCAN concluído.',
            'platform': platform.platform,
            'confidence': int(platform.confidence * 100),
            'score': int(quality.score),
            'rows': int(rows or quality.rows),
            'warnings': [str(item) for item in list(quality.warnings or [])[:5]],
        }
    except Exception:
        return {'title': 'BLINGSMARTSCAN concluído.', 'rows': int(rows or 0), 'warnings': []}


def _store_smartscan_notice(operation: str, report, *, rows: int) -> None:
    payload = _smartscan_notice_payload(report, rows=rows)
    st.session_state[f'blingsmartscan_notice_{operation}'] = payload
    st.session_state['blingsmartscan_last_notice'] = payload


def prepare_raw_urls_for_capture(
    *,
    operation: str,
    raw_urls: str,
    deep_options: dict[str, int | bool] | None,
    progress_bar,
    status_box,
) -> tuple[str, dict[str, object]]:
    options = deep_options or {}
    if _is_stock_balance_only(operation, options) and not _is_stock_full_site_scan(operation, options):
        return raw_urls, {
            'deep_capture_enabled': False,
            'stock_balance_only': True,
            'stock_full_site_scan': False,
            'scan_mode': 'stock_balance_product_links_only',
            'reason': 'Operação de estoque via API usando apenas links de produtos informados, sem varredura profunda.',
        }

    if not bool(options.get('enabled')):
        return raw_urls, {'deep_capture_enabled': False, 'scan_mode': 'full_public_scan'}

    callback = make_site_progress_callback(progress_bar, status_box)
    result = discover_deep_product_urls(
        raw_urls,
        max_pages=int(options.get('max_pages') or STOCK_BALANCE_PAGES_LIMIT),
        max_products=int(options.get('max_products') or STOCK_BALANCE_PRODUCTS_LIMIT),
        max_depth=int(options.get('max_depth') or STOCK_BALANCE_DEPTH_LIMIT),
        budget_seconds=int(options.get('budget_seconds') or DISCOVERY_BUDGET_SECONDS),
        progress_callback=callback,
    )

    base_details = {
        'deep_capture_enabled': True,
        'stock_balance_only': _is_stock_balance_only(operation, options),
        'stock_full_site_scan': _is_stock_full_site_scan(operation, options),
        'deep_capture_found_products': len(result.product_urls),
        'deep_capture_visited_pages': result.visited_pages,
        'deep_capture_scanned_pages': result.scanned_pages,
        'deep_capture_ignored_external_links': result.ignored_external_links,
        'deep_capture_max_depth': result.max_depth,
        'deep_capture_stopped_by_budget': result.stopped_by_budget,
        'deep_capture_stop_reason': result.stop_reason,
    }

    if not result.product_urls:
        base_details['scan_mode'] = 'stock_balance_full_deep_scan_no_links_found' if _is_stock_balance_only(operation, options) else 'full_deep_scan_no_links_found'
        return raw_urls, base_details

    st.session_state[f'site_deep_capture_urls_{operation}'] = result.raw_urls
    st.session_state[f'site_deep_capture_found_{operation}'] = len(result.product_urls)
    base_details['scan_mode'] = 'stock_balance_full_deep_scan' if _is_stock_balance_only(operation, options) else 'full_deep_scan'
    return result.raw_urls, base_details


def capture_limits_for_operation(operation: str, deep_options: dict[str, int | bool] | None) -> tuple[int, int, bool]:
    options = deep_options or {}
    if _is_stock_balance_only(operation, options):
        return (
            min(max(int(options.get('max_pages') or 0), STOCK_BALANCE_PAGES_LIMIT), STOCK_BALANCE_PAGES_LIMIT),
            min(max(int(options.get('max_products') or 0), STOCK_BALANCE_PRODUCTS_LIMIT), STOCK_BALANCE_PRODUCTS_LIMIT),
            True,
        )
    if bool(options.get('enabled')):
        return (
            min(max(int(options.get('max_pages') or 0), ALL_PAGES_LIMIT), ALL_PAGES_LIMIT),
            min(max(int(options.get('max_products') or 0), ALL_PRODUCTS_LIMIT), ALL_PRODUCTS_LIMIT),
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


def _run_current_site_engine(**kwargs) -> pd.DataFrame:
    return run_site_engine(pipeline=load_site_pipeline(), **kwargs)


def _mark_manual_continue(operation: str, rows: int, columns: int) -> None:
    st.session_state['blingsmartscan_manual_continue_required'] = True
    st.session_state['blingsmartscan_ready_to_continue'] = True
    st.session_state['blingsmartscan_continue_target_step'] = _next_step_after_capture()
    st.session_state['blingsmartscan_finished_operation'] = operation
    st.session_state['blingsmartscan_finished_rows'] = int(rows)
    st.session_state['blingsmartscan_finished_columns'] = int(columns)


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
    stock_full_site_scan = _is_stock_full_site_scan(operation, deep_options)
    st.session_state['site_capture_started_at'] = started_at
    set_capture_state(operation=operation, running=True, finished=False)
    max_pages, max_products, all_products = capture_limits_for_operation(operation, deep_options)
    add_audit_event(
        'blingsmartscan_ui_started',
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
            'stock_full_site_scan': stock_full_site_scan,
            'all_products': bool(all_products),
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'scan_goal': 'blingsmartscan_saldo_estoque' if stock_balance_only else 'blingsmartscan_cadastro',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    reset_site_progress()
    progress_text = 'BLINGSMARTSCAN buscando saldos com IA...' if stock_balance_only else 'BLINGSMARTSCAN buscando produtos com IA...'
    progress_bar = st.progress(0, text=progress_text)
    status_box = st.empty()
    deep_details: dict[str, object] = {}
    smart_report = None
    try:
        prepared_urls, deep_details = prepare_raw_urls_for_capture(
            operation=operation,
            raw_urls=raw_urls,
            deep_options=deep_options,
            progress_bar=progress_bar,
            status_box=status_box,
        )
        df_site, smart_report = run_bling_smartscan(
            operation=operation,
            raw_urls=prepared_urls,
            requested_columns=requested_columns,
            engine_runner=_run_current_site_engine,
            all_products=all_products,
            max_pages=max_pages,
            max_products=max_products,
            progress_callback=make_site_progress_callback(progress_bar, status_box),
        )
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        clear_site_df(operation, 'blingsmartscan_exception')
        set_capture_state(operation=operation, running=False, finished=False, error=message)
        finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN encerrado com erro.')
        add_audit_event('blingsmartscan_ui_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'stock_full_site_scan': stock_full_site_scan, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        _orange_notice('O BLINGSMARTSCAN foi interrompido antes de finalizar. O sistema evitou queda total; baixe o log debug para diagnóstico.')
        return

    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        clear_site_df(operation, 'blingsmartscan_vazio')
        empty_message = 'O BLINGSMARTSCAN não encontrou dados válidos nesse lote.'
        set_capture_state(operation=operation, running=False, finished=False, error=empty_message, rows=0, columns=0)
        finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN encerrado sem dados encontrados.')
        add_audit_event('blingsmartscan_ui_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'stock_full_site_scan': stock_full_site_scan, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'responsible_file': RESPONSIBLE_FILE})
        _orange_notice('Nenhum dado válido foi encontrado nesse lote inteligente. Confira o link inicial ou cole links diretos de produtos.')
        return

    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    store_site_df(operation, df_site)
    _persist_operation_state(operation)
    set_capture_state(operation=operation, running=False, finished=True, rows=rows, columns=columns)
    if smart_report is not None:
        try:
            st.session_state[f'blingsmartscan_report_{operation}'] = asdict(smart_report)
        except Exception:
            st.session_state[f'blingsmartscan_report_{operation}'] = {'message': getattr(smart_report, 'message', '')}
        _store_smartscan_notice(operation, smart_report, rows=rows)

    target_step = _next_step_after_capture()
    target_label = _next_step_label_after_capture()
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
        'stock_full_site_scan': stock_full_site_scan,
        'scan_goal': 'blingsmartscan_saldo_estoque' if stock_balance_only else 'blingsmartscan_cadastro',
        'responsible_file': RESPONSIBLE_FILE,
        'manual_continue_required': True,
        'manual_continue_target_step': target_step,
    }
    details.update(deep_details)
    if smart_report is not None:
        details['blingsmartscan_report'] = asdict(smart_report)
    add_audit_event('blingsmartscan_ui_saved_to_state', area='SITE', step='entrada', status='OK', details=details)

    if deep_details.get('deep_capture_stopped_by_budget'):
        st.session_state['blingsmartscan_budget_notice'] = f'O BLINGSMARTSCAN encontrou {rows} produto(s) neste lote e parou para evitar queda do sistema. Você pode rodar outro lote depois.'
    _mark_manual_continue(operation, rows, columns)
    finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN concluído. Resultado salvo.')
    st.success(f'BLINGSMARTSCAN concluiu e salvou {rows} produto(s). Toque em Continuar para ir para {target_label}.')


__all__ = ['capture_limits_for_operation', 'run_site_capture']
