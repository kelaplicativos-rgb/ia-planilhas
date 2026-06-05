from __future__ import annotations

import time
from dataclasses import asdict

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_site_capture_adapter import fail_site_capture, finish_site_capture, start_site_capture
from bling_app_zero.agents.site_capture_agent import run_bling_smartscan
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.intelligent_flow_decision import decide_after_site_capture
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
from bling_app_zero.ui.site_progress import append_site_progress, make_site_progress_callback, reset_site_progress

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


def _safe_progress(progress, value: int, text: str) -> None:
    if progress is None:
        return
    try:
        progress.progress(max(0, min(100, int(value))), text=text)
    except Exception:
        pass


def _safe_status(status_box, text: str) -> None:
    if status_box is None:
        return
    try:
        status_box.caption(text)
    except Exception:
        pass


def _emit_capture_progress(stage: str, message: str, *, progress: float | None = None, **details) -> None:
    payload = {
        'stage': stage,
        'message': message,
        'progress': progress if progress is not None else details.pop('progress_value', 0.0),
    }
    payload.update(details)
    try:
        append_site_progress(payload)
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
        payload = {
            'title': 'BLINGSMARTSCAN concluído.',
            'platform': platform.platform,
            'confidence': int(platform.confidence * 100),
            'score': int(quality.score),
            'rows': int(rows or quality.rows),
            'warnings': [str(item) for item in list(quality.warnings or [])[:5]],
        }
        decision = getattr(report, 'decision', None)
        if decision is not None:
            payload['decision'] = decision.to_dict() if hasattr(decision, 'to_dict') else decision
        return payload
    except Exception:
        return {'title': 'BLINGSMARTSCAN concluído.', 'rows': int(rows or 0), 'warnings': []}


def _store_smartscan_notice(operation: str, report, *, rows: int) -> None:
    payload = _smartscan_notice_payload(report, rows=rows)
    st.session_state[f'blingsmartscan_notice_{operation}'] = payload
    st.session_state['blingsmartscan_last_notice'] = payload


def _progress_callback_for_capture(*, operation: str, options: dict[str, int | bool], progress_bar, status_box):
    if _is_stock_balance_only(operation, options):
        return None
    return make_site_progress_callback(progress_bar, status_box)


def _decision_from_smart_report(operation: str, smart_report):
    if smart_report is None:
        return None
    try:
        existing = getattr(smart_report, 'decision', None)
        if existing is not None:
            return existing
        platform = getattr(getattr(smart_report, 'platform', None), 'platform', '')
        used_api = bool(getattr(smart_report, 'used_api', False))
        return decide_after_site_capture(
            operation=operation,
            quality=getattr(smart_report, 'quality', None),
            used_api=used_api,
            platform=platform,
        )
    except Exception:
        return None


def _render_capture_decision(operation: str, smart_report, *, rows: int) -> dict[str, object]:
    decision = _decision_from_smart_report(operation, smart_report)
    if decision is None:
        return {'action': 'REVISAR', 'status': 'ATENCAO', 'should_block': False, 'should_recapture': False}

    payload = decision.to_dict()
    st.session_state[f'blingsmartscan_decision_{operation}'] = payload
    st.session_state['blingsmartscan_last_decision'] = payload

    if decision.status == 'BLOQUEADO':
        st.error(f'{decision.title}: {decision.message}')
    elif decision.status == 'ATENCAO':
        st.warning(f'{decision.title}: {decision.message}')
    else:
        st.success(f'{decision.title}: {decision.message}')

    if decision.reasons:
        with st.expander('Decisão inteligente da captura', expanded=False):
            for reason in decision.reasons[:10]:
                st.caption(f'• {reason}')

    _emit_capture_progress(
        'Decisão inteligente',
        f'{decision.title}: {decision.message}',
        progress=0.90,
        rows=int(rows),
        action=decision.action,
        status=decision.status,
        next_step=decision.next_step,
    )
    add_audit_event(
        'blingsmartscan_ui_intelligent_decision',
        area='SITE',
        step='decisao',
        status=decision.status,
        details={'operation': operation, 'rows': int(rows), 'decision': payload, 'responsible_file': RESPONSIBLE_FILE},
    )
    return payload


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
        _emit_capture_progress(
            'Entrada validada',
            'Usando somente os links informados, sem varredura profunda.',
            progress=0.08,
            stock_balance_only=True,
        )
        return raw_urls, {
            'deep_capture_enabled': False,
            'stock_balance_only': True,
            'stock_full_site_scan': False,
            'scan_mode': 'stock_balance_product_links_only',
            'reason': 'Operação de estoque via API usando apenas links de produtos informados, sem varredura profunda.',
        }

    if not bool(options.get('enabled')):
        _emit_capture_progress('Entrada validada', 'Varredura profunda desativada. Enviando links informados para leitura.', progress=0.08)
        return raw_urls, {'deep_capture_enabled': False, 'scan_mode': 'full_public_scan'}

    callback = _progress_callback_for_capture(operation=operation, options=options, progress_bar=progress_bar, status_box=status_box)
    _emit_capture_progress(
        'Descoberta de produtos',
        'Abrindo o link inicial e procurando páginas reais de produto.',
        progress=0.14,
        max_pages=int(options.get('max_pages') or STOCK_BALANCE_PAGES_LIMIT),
        max_products=int(options.get('max_products') or STOCK_BALANCE_PRODUCTS_LIMIT),
        max_depth=int(options.get('max_depth') or STOCK_BALANCE_DEPTH_LIMIT),
        budget_seconds=int(options.get('budget_seconds') or DISCOVERY_BUDGET_SECONDS),
    )
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
        'progress_mode': 'lightweight_mobile_safe' if _is_stock_balance_only(operation, options) else 'live',
    }
    _emit_capture_progress(
        'Produtos localizados',
        f'Foram localizados {len(result.product_urls)} link(s) de produto. Agora o sistema vai extrair os saldos.',
        progress=0.42,
        urls_found=len(result.product_urls),
        visited_pages=result.visited_pages,
        scanned_pages=result.scanned_pages,
        deep_capture_found_products=len(result.product_urls),
        deep_capture_visited_pages=result.visited_pages,
        deep_capture_scanned_pages=result.scanned_pages,
        deep_capture_stopped_by_budget=result.stopped_by_budget,
    )

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


def _capture_context(raw_urls: str, operation: str, max_pages: int = 0, max_products: int = 0, *, api_mode: bool | None = None) -> dict[str, object]:
    return {
        'url': raw_urls,
        'operation': operation,
        'mode': operation,
        'max_pages': int(max_pages or 0),
        'max_products': int(max_products or 0),
        'api_mode': active_contract().is_api if api_mode is None else bool(api_mode),
        'send_to_bling': active_contract().is_api if api_mode is None else bool(api_mode),
    }


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
        fail_site_capture('Cole pelo menos um link para buscar.', _capture_context(raw_urls, operation))
        st.warning('Cole pelo menos um link para buscar.')
        add_audit_event('site_capture_blocked_missing_urls', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'responsible_file': RESPONSIBLE_FILE})
        return
    if _missing_model_blocked(operation, requested_columns):
        clear_site_df(operation, 'busca_sem_modelo_destino')
        fail_site_capture('Busca bloqueada: modelo de destino ausente.', _capture_context(raw_urls, operation))
        st.error('Busca bloqueada: modelo de destino ausente.')
        add_audit_event('site_capture_blocked_missing_model', area='SITE', step='entrada', status='BLOQUEADO', details={'operation': operation, 'feature_contract': active_contract().key, 'responsible_file': RESPONSIBLE_FILE})
        return

    options = deep_options or {}
    started_at = time.time()
    stock_balance_only = _is_stock_balance_only(operation, options)
    stock_full_site_scan = _is_stock_full_site_scan(operation, options)
    st.session_state['site_capture_started_at'] = started_at
    set_capture_state(operation=operation, running=True, finished=False)
    max_pages, max_products, all_products = capture_limits_for_operation(operation, options)
    start_site_capture(_capture_context(raw_urls, operation, max_pages, max_products))
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
            'deep_capture_requested': bool(options.get('enabled')),
            'stock_balance_only': stock_balance_only,
            'stock_full_site_scan': stock_full_site_scan,
            'all_products': bool(all_products),
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'scan_goal': 'blingsmartscan_saldo_estoque' if stock_balance_only else 'blingsmartscan_cadastro',
            'progress_mode': 'lightweight_mobile_safe' if stock_balance_only else 'live',
            'neutral_capture_state': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    reset_site_progress()
    _emit_capture_progress(
        'Início da busca',
        'Captura iniciada. Validando operação, contrato ativo, depósito e limites seguros.',
        progress=0.03,
        max_pages=int(max_pages),
        max_products=int(max_products),
        stock_balance_only=stock_balance_only,
        stock_full_site_scan=stock_full_site_scan,
    )

    if stock_balance_only:
        progress_bar = st.progress(3, text='Preparando busca segura de saldos...')
        status_box = st.empty()
        _safe_status(status_box, 'Modo seguro: a barra atualiza por etapas para não travar o celular.')
        st.info('Busca de saldos em modo seguro. A barra acompanha etapas principais e o resultado é salvo ao final.')
    else:
        progress_bar = st.progress(0, text='BLINGSMARTSCAN buscando produtos com IA...')
        status_box = st.empty()

    deep_details: dict[str, object] = {}
    smart_report = None
    try:
        _safe_progress(progress_bar, 12 if stock_balance_only else 0, 'Localizando produtos no site...')
        _safe_status(status_box, 'Etapa 1 de 3: localizando links/produtos.')
        _emit_capture_progress('Etapa 1 de 3', 'Localizando links/produtos no site.', progress=0.12)
        prepared_urls, deep_details = prepare_raw_urls_for_capture(
            operation=operation,
            raw_urls=raw_urls,
            deep_options=options,
            progress_bar=progress_bar,
            status_box=status_box,
        )
        found = int(deep_details.get('deep_capture_found_products') or 0) if isinstance(deep_details, dict) else 0
        if stock_balance_only:
            found_text = f' · {found} produto(s) localizado(s)' if found else ''
            _safe_progress(progress_bar, 45, f'Produtos localizados. Extraindo saldos{found_text}...')
            _safe_status(status_box, f'Etapa 2 de 3: extraindo dados de estoque{found_text}.')
        _emit_capture_progress(
            'Etapa 2 de 3',
            f'Extraindo dados de estoque dos produtos localizados ({found} encontrado(s)).',
            progress=0.48,
            urls_found=found,
            deep_capture_found_products=found,
            deep_capture_visited_pages=deep_details.get('deep_capture_visited_pages', ''),
            deep_capture_scanned_pages=deep_details.get('deep_capture_scanned_pages', ''),
        )
        capture_callback = _progress_callback_for_capture(operation=operation, options=options, progress_bar=progress_bar, status_box=status_box)
        df_site, smart_report = run_bling_smartscan(
            operation=operation,
            raw_urls=prepared_urls,
            requested_columns=requested_columns,
            engine_runner=_run_current_site_engine,
            all_products=all_products,
            max_pages=max_pages,
            max_products=max_products,
            progress_callback=capture_callback,
        )
        rows_now = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
        _emit_capture_progress(
            'Extração concluída',
            f'Leitura encerrada. Foram gerada(s) {rows_now} linha(s) para validação.',
            progress=0.78,
            rows=rows_now,
            found=rows_now,
            elapsed_seconds=round(time.time() - started_at, 2),
        )
        if stock_balance_only:
            _safe_progress(progress_bar, 82, 'Validando e salvando resultado da busca...')
            _safe_status(status_box, 'Etapa 3 de 3: validando e salvando resultado.')
        _emit_capture_progress('Etapa 3 de 3', 'Validando colunas, depósito, saldos e salvando resultado final.', progress=0.86, rows=rows_now)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        _emit_capture_progress('Erro na captura', message, progress=0.0, errors=1, elapsed_seconds=round(time.time() - started_at, 2))
        clear_site_df(operation, 'blingsmartscan_exception')
        set_capture_state(operation=operation, running=False, finished=False, error=message)
        fail_site_capture(message, _capture_context(raw_urls, operation, max_pages, max_products))
        finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN encerrado com erro.')
        add_audit_event('blingsmartscan_ui_failed', area='SITE', step='entrada', status='ERRO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'stock_full_site_scan': stock_full_site_scan, 'error': message, 'error_type': exc.__class__.__name__, 'elapsed_seconds': round(time.time() - started_at, 2), 'progress_mode': 'lightweight_mobile_safe' if stock_balance_only else 'live', 'neutral_capture_state': True, 'responsible_file': RESPONSIBLE_FILE})
        _orange_notice('O BLINGSMARTSCAN foi interrompido antes de finalizar. O sistema evitou queda total; baixe o log debug para diagnóstico.')
        return

    rows = len(df_site) if isinstance(df_site, pd.DataFrame) else 0
    columns = len(df_site.columns) if isinstance(df_site, pd.DataFrame) else 0
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        _emit_capture_progress('Sem dados válidos', 'Nenhuma linha válida foi gerada para este lote.', progress=0.0, rows=0, columns=0)
        clear_site_df(operation, 'blingsmartscan_vazio')
        empty_message = 'O BLINGSMARTSCAN não encontrou dados válidos nesse lote.'
        set_capture_state(operation=operation, running=False, finished=False, error=empty_message, rows=0, columns=0)
        fail_site_capture(empty_message, _capture_context(raw_urls, operation, max_pages, max_products))
        finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN encerrado sem dados encontrados.')
        add_audit_event('blingsmartscan_ui_empty', area='SITE', step='entrada', status='AVISO', details={'operation': operation, 'stock_balance_only': stock_balance_only, 'stock_full_site_scan': stock_full_site_scan, 'rows': rows, 'columns': columns, 'elapsed_seconds': round(time.time() - started_at, 2), 'progress_mode': 'lightweight_mobile_safe' if stock_balance_only else 'live', 'neutral_capture_state': True, 'responsible_file': RESPONSIBLE_FILE})
        _orange_notice('Nenhum dado válido foi encontrado nesse lote inteligente. Confira o link inicial ou cole links diretos de produtos.')
        return

    flow_decision = _render_capture_decision(operation, smart_report, rows=rows)
    if bool(flow_decision.get('should_block')) or bool(flow_decision.get('should_recapture')):
        clear_site_df(operation, 'blingsmartscan_decisao_bloqueada')
        set_capture_state(operation=operation, running=False, finished=False, error=str(flow_decision.get('message') or 'Decisão inteligente bloqueou o avanço.'), rows=rows, columns=columns)
        fail_site_capture(str(flow_decision.get('message') or 'Decisão inteligente bloqueou o avanço.'), _capture_context(raw_urls, operation, max_pages, max_products))
        finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN aguardando correção da captura.')
        st.warning('A captura foi protegida e não avançou automaticamente. Revise os links ou rode uma nova captura com dados mais completos.')
        return

    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    store_site_df(operation, df_site)
    finish_site_capture(
        df_site,
        _capture_context(raw_urls, operation, max_pages, max_products),
        report_key=f'blingsmartscan_report_{operation}',
        message=f'BLINGSMARTSCAN concluiu e salvou {rows} produto(s).',
    )
    _persist_operation_state(operation)
    set_capture_state(operation=operation, running=False, finished=True, rows=rows, columns=columns)
    if smart_report is not None:
        try:
            report_payload = asdict(smart_report)
            report_payload['flow_decision'] = flow_decision
            st.session_state[f'blingsmartscan_report_{operation}'] = report_payload
        except Exception:
            st.session_state[f'blingsmartscan_report_{operation}'] = {'message': getattr(smart_report, 'message', ''), 'flow_decision': flow_decision}
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
        'progress_mode': 'lightweight_mobile_safe' if stock_balance_only else 'live',
        'neutral_capture_state': True,
        'responsible_file': RESPONSIBLE_FILE,
        'manual_continue_required': True,
        'manual_continue_target_step': target_step,
        'flow_decision': flow_decision,
    }
    details.update(deep_details)
    if smart_report is not None:
        details['blingsmartscan_report'] = asdict(smart_report)
    add_audit_event('blingsmartscan_ui_saved_to_state', area='SITE', step='entrada', status=str(flow_decision.get('status') or 'OK'), details=details)

    if deep_details.get('deep_capture_stopped_by_budget'):
        st.session_state['blingsmartscan_budget_notice'] = f'O BLINGSMARTSCAN encontrou {rows} produto(s) neste lote e parou para evitar queda do sistema. Você pode rodar outro lote depois.'
    _emit_capture_progress('Resultado salvo', f'Busca concluída. {rows} linha(s) e {columns} coluna(s) salvas para o próximo passo.', progress=1.0, rows=rows, columns=columns, elapsed_seconds=round(time.time() - started_at, 2))
    _mark_manual_continue(operation, rows, columns)
    finish_progress(progress_bar, status_box, text='BLINGSMARTSCAN concluído. Resultado salvo.')
    st.success(f'BLINGSMARTSCAN concluiu e salvou {rows} produto(s). Toque em Continuar para ir para {target_label}.')


__all__ = ['capture_limits_for_operation', 'run_site_capture']
