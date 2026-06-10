from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.interaction_guard import (
    activate_logout_guard,
    clear_logout_guard,
    disconnect_backend_token,
    logout_guard_active,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/blingfix_runtime_patches.py'
_PATCH_INSTALLED_KEY = 'blingfix_runtime_patches_installed_v8'
MAX_BLING_IMAGES_PER_PRODUCT = 6
_IMAGE_LIST_KEYS = {'imagens', 'images', 'imagensurl', 'externas', 'externos', 'fotos'}


SITE_API_CAPTURE_POLICIES: dict[str, dict[str, Any]] = {
    'cadastro': {'max_pages': 12, 'max_products': 40, 'max_depth': 1, 'send_mode': 'produto'},
    'estoque': {'max_pages': 12, 'max_products': 80, 'max_depth': 1, 'send_mode': 'estoque'},
    'atualizacao_preco': {'max_pages': 12, 'max_products': 60, 'max_depth': 1, 'send_mode': 'preco'},
}
DIRECT_API_SITE_OPERATIONS = set(SITE_API_CAPTURE_POLICIES)


def _site_api_policy(operation: object) -> dict[str, Any]:
    operation_key = _normalize_operation(operation)
    return dict(SITE_API_CAPTURE_POLICIES.get(operation_key) or SITE_API_CAPTURE_POLICIES['cadastro'])


def _patch_oauth_callback() -> None:
    from bling_app_zero.core import bling_oauth

    original: Callable[..., Any] | None = getattr(bling_oauth, '_blingfix_original_process_oauth_callback', None)
    if original is None:
        original = bling_oauth.process_oauth_callback
        setattr(bling_oauth, '_blingfix_original_process_oauth_callback', original)

    def guarded_process_oauth_callback() -> None:
        try:
            qp = getattr(st, 'query_params', {})
            code = str(qp.get('code') or '').strip() if hasattr(qp, 'get') else ''
            error = str(qp.get('error') or '').strip() if hasattr(qp, 'get') else ''
            if code or error:
                clear_logout_guard('oauth_callback_received')
        except Exception:
            pass
        original()

    bling_oauth.process_oauth_callback = guarded_process_oauth_callback


def _patch_disconnect() -> None:
    from bling_app_zero.core import bling_oauth
    from bling_app_zero.ui import home_bling_api_flow

    original: Callable[..., Any] | None = getattr(bling_oauth, '_blingfix_original_disconnect', None)
    if original is None:
        original = bling_oauth.disconnect
        setattr(bling_oauth, '_blingfix_original_disconnect', original)

    def guarded_disconnect() -> None:
        activate_logout_guard('manual_disconnect')
        try:
            original()
        finally:
            disconnect_backend_token()
            activate_logout_guard('manual_disconnect_after_clear')
            add_audit_event('bling_disconnect_guarded_runtime', area='BLING_OAUTH', status='OK', details={'responsible_file': RESPONSIBLE_FILE})

    bling_oauth.disconnect = guarded_disconnect
    home_bling_api_flow.disconnect = guarded_disconnect


def _patch_site_operation_guard() -> None:
    from bling_app_zero.ui import site_panel, site_panel_state

    original: Callable[..., Any] | None = getattr(site_panel_state, '_blingfix_original_get_site_df', None)
    if original is None:
        original = site_panel_state.get_site_df
        setattr(site_panel_state, '_blingfix_original_get_site_df', original)

    def guarded_get_site_df(operation: str):
        requested = _normalize_operation(operation)
        captured = _normalize_operation(st.session_state.get('site_capture_operation'))
        if requested and captured and requested != captured:
            add_audit_event('site_panel_ignored_df_from_other_operation', area='SITE', step='entrada', status='INFO', details={'requested_operation': requested, 'site_capture_operation': captured, 'reason': 'evitar_estoque_usar_captura_de_cadastro', 'responsible_file': RESPONSIBLE_FILE})
            return None
        return original(operation)

    site_panel_state.get_site_df = guarded_get_site_df
    site_panel.get_site_df = guarded_get_site_df


def _patch_stock_site_origin_filter() -> None:
    try:
        from bling_app_zero.pipelines import site_pipeline_blingfix
        from bling_app_zero.pipelines.stock_api_origin_guard import filter_origin_rows_for_operation

        def guarded_filter_live_origin_rows(df, raw_urls: str):
            operation = str(st.session_state.get('active_feature_operation') or st.session_state.get('flow_spine_operation') or st.session_state.get('operacao_final') or '')
            return filter_origin_rows_for_operation(df, raw_urls, operation=operation)

        site_pipeline_blingfix._filter_live_origin_rows = guarded_filter_live_origin_rows
        add_audit_event(
            'stock_api_origin_url_filter_runtime_patch_installed',
            area='SITE',
            status='OK',
            details={'target': 'site_pipeline_blingfix._filter_live_origin_rows', 'reason': 'Estoque/API não deve zerar linhas sem URL quando há identificador e quantidade.', 'responsible_file': RESPONSIBLE_FILE},
        )
    except Exception as exc:
        add_audit_event('stock_api_origin_url_filter_runtime_patch_failed', area='SITE', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


def _is_direct_api_operation(module: Any, operation: object) -> bool:
    operation_key = _normalize_operation(operation)
    try:
        contract = module.active_contract()
        return bool(contract.is_api and contract.operation == operation_key and operation_key in DIRECT_API_SITE_OPERATIONS)
    except Exception:
        return False


def _force_site_api_options(module: Any, operation: object, options: dict[str, Any] | None) -> dict[str, Any]:
    forced = dict(options or {})
    operation_key = _normalize_operation(operation)
    if not _is_direct_api_operation(module, operation_key):
        return forced
    policy = _site_api_policy(operation_key)
    forced.update(
        {
            'enabled': True,
            'max_pages': int(policy['max_pages']),
            'max_products': int(policy['max_products']),
            'max_depth': int(policy['max_depth']),
            'scan_total_ui': True,
            'stock_balance_only': operation_key == 'estoque',
            'stock_full_site_scan': False,
            'stock_api_fast_batch': operation_key == 'estoque',
            'stock_api_skip_predeep_discovery': operation_key == 'estoque',
            'cadastro_api_fast_batch': operation_key == 'cadastro',
            'cadastro_api_skip_predeep_discovery': operation_key == 'cadastro',
            'price_api_fast_batch': operation_key == 'atualizacao_preco',
            'price_api_skip_predeep_discovery': operation_key == 'atualizacao_preco',
            'skip_predeep_discovery': True,
            'unified_api_site_engine': True,
            'api_site_batch_contract': operation_key,
            'api_site_send_mode': str(policy['send_mode']),
            'site_api_capture_policy': 'runtime_v8_unified_site_api_short_batch',
            'api_direct_first_batch_only': True,
            'disable_deep_extraction_after_discovery': True,
            'budget_seconds': 20,
        }
    )
    return forced


def _patch_unified_site_api_runtime_guard() -> None:
    try:
        from bling_app_zero.ui import site_panel, site_panel_capture

        if getattr(site_panel_capture, '_blingfix_v8_unified_site_api_guard', False):
            return

        site_panel.SITE_API_CAPTURE_POLICIES = SITE_API_CAPTURE_POLICIES
        site_panel.DIRECT_API_SITE_OPERATIONS = DIRECT_API_SITE_OPERATIONS
        site_panel.SUPPORTED_SITE_OPERATIONS = {*DIRECT_API_SITE_OPERATIONS, site_panel.UNIVERSAL_OPERATION}

        def direct_api_site_mode(operation: str) -> bool:
            return _is_direct_api_operation(site_panel, operation)

        def api_site_max_pages(operation: str) -> int:
            return int(_site_api_policy(operation)['max_pages'])

        def api_site_max_products(operation: str) -> int:
            return int(_site_api_policy(operation)['max_products'])

        def api_site_max_depth(operation: str) -> int:
            return int(_site_api_policy(operation)['max_depth'])

        def api_site_send_mode(operation: str) -> str:
            return str(_site_api_policy(operation)['send_mode'])

        def scan_total_options(operation: str) -> dict[str, Any]:
            if direct_api_site_mode(operation):
                return _force_site_api_options(site_panel, operation, {})
            return {
                'enabled': True,
                'max_pages': getattr(site_panel, 'SCAN_TOTAL_MAX_PAGES', 120),
                'max_products': getattr(site_panel, 'SCAN_TOTAL_MAX_PRODUCTS', 500),
                'max_depth': getattr(site_panel, 'SCAN_TOTAL_MAX_DEPTH', 2),
                'scan_total_ui': True,
                'stock_balance_only': False,
                'stock_full_site_scan': False,
                'stock_api_fast_batch': False,
                'stock_api_skip_predeep_discovery': False,
                'cadastro_api_fast_batch': False,
                'cadastro_api_skip_predeep_discovery': False,
                'price_api_fast_batch': False,
                'price_api_skip_predeep_discovery': False,
                'skip_predeep_discovery': False,
                'unified_api_site_engine': False,
                'api_site_batch_contract': '',
                'api_site_send_mode': '',
                'site_api_capture_policy': 'public_full_scan',
                'budget_seconds': getattr(site_panel, 'SITE_PANEL_DISCOVERY_BUDGET_SECONDS', 45),
            }

        def render_scan_total_notice(operation: str) -> None:
            if direct_api_site_mode(operation):
                op = _normalize_operation(operation)
                if op == 'atualizacao_preco':
                    site_panel.orange_warning('Preço/API usa busca única em lote curto: captura rápida de preço sem travar nos 42%.')
                elif op == 'estoque':
                    site_panel.orange_warning('Estoque/API usa busca única em lote curto: captura rápida de saldo sem travar nos 42%.')
                else:
                    site_panel.orange_warning('Cadastro/API usa busca única em lote curto: captura rápida para liberar envio ao Bling.')
                return
            site_panel.orange_warning('Busca completa ativa: o sistema procura produtos no site e captura os dados conforme o contrato ativo.')

        site_panel._is_direct_api_site_mode = direct_api_site_mode
        site_panel._api_site_max_pages = api_site_max_pages
        site_panel._api_site_max_products = api_site_max_products
        site_panel._api_site_max_depth = api_site_max_depth
        site_panel._api_site_send_mode = api_site_send_mode
        site_panel._scan_total_options = scan_total_options
        site_panel._render_scan_total_notice = render_scan_total_notice

        original_run_site_capture = site_panel_capture.run_site_capture
        original_engine_runner = site_panel_capture._run_current_site_engine

        def skip_predeep_discovery(operation: str, options: dict[str, Any]) -> bool:
            if bool(options.get('skip_predeep_discovery') or options.get('price_api_skip_predeep_discovery')):
                return True
            return _is_direct_api_operation(site_panel_capture, operation)

        def capture_limits_for_operation(operation: str, deep_options: dict[str, Any] | None) -> tuple[int, int, bool]:
            options = _force_site_api_options(site_panel_capture, operation, deep_options)
            if _is_direct_api_operation(site_panel_capture, operation):
                policy = _site_api_policy(operation)
                return int(policy['max_pages']), int(policy['max_products']), True
            if site_panel_capture._is_stock_balance_only(operation, options):
                return (
                    min(max(int(options.get('max_pages') or 0), site_panel_capture.STOCK_BALANCE_PAGES_LIMIT), site_panel_capture.STOCK_BALANCE_PAGES_LIMIT),
                    min(max(int(options.get('max_products') or 0), site_panel_capture.STOCK_BALANCE_PRODUCTS_LIMIT), site_panel_capture.STOCK_BALANCE_PRODUCTS_LIMIT),
                    True,
                )
            if bool(options.get('enabled')):
                return (
                    min(max(int(options.get('max_pages') or 0), site_panel_capture.ALL_PAGES_LIMIT), site_panel_capture.ALL_PAGES_LIMIT),
                    min(max(int(options.get('max_products') or 0), site_panel_capture.ALL_PRODUCTS_LIMIT), site_panel_capture.ALL_PRODUCTS_LIMIT),
                    True,
                )
            return site_panel_capture.ALL_PAGES_LIMIT, site_panel_capture.ALL_PRODUCTS_LIMIT, True

        def guarded_engine_runner(**kwargs):
            operation = _normalize_operation(kwargs.get('operation'))
            if _is_direct_api_operation(site_panel_capture, operation):
                policy = _site_api_policy(operation)
                kwargs['all_products'] = True
                kwargs['max_pages'] = min(int(kwargs.get('max_pages') or policy['max_pages']), int(policy['max_pages']))
                kwargs['max_products'] = min(int(kwargs.get('max_products') or policy['max_products']), int(policy['max_products']))
                kwargs['max_depth'] = min(int(kwargs.get('max_depth') or policy['max_depth']), int(policy['max_depth']))
                add_audit_event(
                    'site_api_42_percent_extraction_guard_applied',
                    area='SITE',
                    step='entrada',
                    status='OK',
                    details={'operation': operation, 'max_pages': kwargs['max_pages'], 'max_products': kwargs['max_products'], 'max_depth': kwargs['max_depth'], 'site_api_capture_policy': 'runtime_v8_unified_site_api_short_batch', 'responsible_file': RESPONSIBLE_FILE},
                )
            return original_engine_runner(**kwargs)

        def guarded_run_site_capture(*, operation: str, raw_urls: str, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, deep_options=None) -> None:
            options = _force_site_api_options(site_panel_capture, operation, deep_options)
            if _is_direct_api_operation(site_panel_capture, operation):
                add_audit_event(
                    'site_api_unified_capture_options_forced',
                    area='SITE',
                    step='entrada',
                    status='OK',
                    details={'operation': operation, 'feature_contract': getattr(site_panel_capture.active_contract(), 'key', ''), 'max_pages': int(options.get('max_pages') or 0), 'max_products': int(options.get('max_products') or 0), 'max_depth': int(options.get('max_depth') or 0), 'skip_predeep_discovery': bool(options.get('skip_predeep_discovery')), 'unified_api_site_engine': bool(options.get('unified_api_site_engine')), 'api_site_batch_contract': options.get('api_site_batch_contract', ''), 'api_site_send_mode': options.get('api_site_send_mode', ''), 'site_api_capture_policy': options.get('site_api_capture_policy', ''), 'responsible_file': RESPONSIBLE_FILE},
                )
            return original_run_site_capture(operation=operation, raw_urls=raw_urls, requested_columns=requested_columns, df_modelo_cadastro=df_modelo_cadastro, df_modelo_estoque=df_modelo_estoque, df_modelo=df_modelo, deep_options=options)

        site_panel_capture.DIRECT_API_SITE_OPERATIONS = DIRECT_API_SITE_OPERATIONS
        site_panel_capture.DIRECT_API_SITE_LIMITS = {op: {'max_pages': int(policy['max_pages']), 'max_products': int(policy['max_products'])} for op, policy in SITE_API_CAPTURE_POLICIES.items()}
        site_panel_capture._skip_predeep_discovery = skip_predeep_discovery
        site_panel_capture.capture_limits_for_operation = capture_limits_for_operation
        site_panel_capture._run_current_site_engine = guarded_engine_runner
        site_panel_capture.run_site_capture = guarded_run_site_capture
        site_panel.run_site_capture = guarded_run_site_capture
        site_panel_capture._blingfix_v8_unified_site_api_guard = True

        add_audit_event('site_api_runtime_guard_v8_installed', area='SITE', step='entrada', status='OK', details={'operations': sorted(DIRECT_API_SITE_OPERATIONS), 'policies': SITE_API_CAPTURE_POLICIES, 'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('site_api_runtime_guard_v8_failed', area='SITE', step='entrada', status='ERRO', details={'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE})


def _looks_like_product_catalog_df(df: Any) -> bool:
    try:
        columns = {str(col or '').strip().lower() for col in getattr(df, 'columns', [])}
    except Exception:
        return False
    product_markers = {'nome', 'produto', 'titulo', 'título', 'descricao', 'descrição', 'descricao_curta', 'preco', 'preço', 'marca', 'categoria', 'imagens', 'imagem', 'url', 'link'}
    stock_only = {'quantidade', 'id', 'codigo', 'código', 'gtin', 'deposito', 'depósito'}
    if columns and columns.issubset(stock_only):
        return False
    return len(columns.intersection(product_markers)) >= 2


def _forced_api_operation(download_df: Any, operation: object) -> str:
    requested = _normalize_operation(operation)
    explicit = _normalize_operation(st.session_state.get('operation') or st.session_state.get('selected_operation') or st.session_state.get('bling_operation') or st.session_state.get('flow_operation'))
    if requested == 'cadastro' or explicit == 'cadastro':
        return 'cadastro'
    if _looks_like_product_catalog_df(download_df):
        return 'cadastro'
    return requested or explicit or 'cadastro'


def _patch_api_batch_operation_guard() -> None:
    from bling_app_zero.ui import bling_api_batch_panel

    original_render: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_blingfix_original_render_bling_api_batch_panel', None)
    if original_render is None:
        original_render = bling_api_batch_panel.render_bling_api_batch_panel
        setattr(bling_api_batch_panel, '_blingfix_original_render_bling_api_batch_panel', original_render)

    original_spine: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_blingfix_original_spine_operation_or', None)
    if original_spine is None:
        original_spine = bling_api_batch_panel._spine_operation_or
        setattr(bling_api_batch_panel, '_blingfix_original_spine_operation_or', original_spine)

    def guarded_spine_operation_or(operation: str) -> str:
        requested = _normalize_operation(operation)
        if requested == 'cadastro':
            return 'cadastro'
        return original_spine(operation)

    def guarded_render_bling_api_batch_panel(download_df, operation: str, key: str, signature: str, rules_sig: str) -> None:
        forced = _forced_api_operation(download_df, operation)
        if forced != _normalize_operation(operation):
            add_audit_event('bling_api_batch_operation_forced_to_cadastro', area='BLING_ENVIO', status='OK', details={'original_operation': operation, 'forced_operation': forced, 'columns': [str(c) for c in getattr(download_df, 'columns', [])], 'reason': 'evitar_site_produto_ser_enviado_como_estoque_api', 'responsible_file': RESPONSIBLE_FILE})
        return original_render(download_df, forced, key, signature, rules_sig)

    bling_api_batch_panel._spine_operation_or = guarded_spine_operation_or
    bling_api_batch_panel.render_bling_api_batch_panel = guarded_render_bling_api_batch_panel


def _is_bling_api_url(url: object) -> bool:
    text = str(url or '').lower()
    return 'bling.com.br' in text and '/produtos' in text


def _image_key(key: object) -> bool:
    normalized = str(key or '').strip().lower().replace('_', '').replace('-', '')
    return normalized in _IMAGE_LIST_KEYS


def _sanitize_bling_images(value: Any, *, parent_key: str = '') -> tuple[Any, int]:
    if isinstance(value, dict):
        changed = 0
        out: dict[Any, Any] = {}
        for key, item in value.items():
            sanitized, item_changed = _sanitize_bling_images(item, parent_key=str(key))
            out[key] = sanitized
            changed += item_changed
        return out, changed

    if isinstance(value, list):
        changed = 0
        out = []
        for item in value:
            sanitized, item_changed = _sanitize_bling_images(item, parent_key=parent_key)
            out.append(sanitized)
            changed += item_changed
        if _image_key(parent_key) and len(out) > MAX_BLING_IMAGES_PER_PRODUCT:
            changed += len(out) - MAX_BLING_IMAGES_PER_PRODUCT
            out = out[:MAX_BLING_IMAGES_PER_PRODUCT]
        return out, changed

    return value, 0


def _sanitize_any_bling_payload(payload: Any) -> Any:
    sanitized, _removed = _sanitize_bling_images(deepcopy(payload))
    return sanitized


def _sanitize_bling_request_json(url: object, payload: Any) -> tuple[Any, int]:
    if not isinstance(payload, (dict, list)) or not _is_bling_api_url(url):
        return payload, 0
    try:
        return _sanitize_bling_images(deepcopy(payload))
    except Exception:
        return payload, 0


def _patch_bling_image_limit_guard() -> None:
    import requests

    original_request: Callable[..., Any] | None = getattr(requests, '_blingfix_original_request', None)
    if original_request is None:
        original_request = requests.request
        setattr(requests, '_blingfix_original_request', original_request)

    def guarded_request(method: str | bytes, url: object, *args: Any, **kwargs: Any):
        payload = kwargs.get('json')
        sanitized, removed = _sanitize_bling_request_json(url, payload)
        if removed:
            kwargs['json'] = sanitized
            add_audit_event('bling_image_limit_guard_applied', area='BLING_ENVIO', status='CORRIGIDO', details={'method': str(method).upper(), 'url_preview': str(url)[:160], 'max_images_per_product': MAX_BLING_IMAGES_PER_PRODUCT, 'removed_images': removed, 'reason': 'Bling bloqueia produto com mais de 6 imagens. Payload limitado antes do envio.', 'responsible_file': RESPONSIBLE_FILE})
        return original_request(method, url, *args, **kwargs)

    requests.request = guarded_request

    def _method_wrapper(method_name: str):
        def wrapped(url: object, *args: Any, **kwargs: Any):
            return guarded_request(method_name.upper(), url, *args, **kwargs)
        return wrapped

    requests.post = _method_wrapper('POST')
    requests.put = _method_wrapper('PUT')
    requests.patch = _method_wrapper('PATCH')


def _patch_internal_image_payload_previews() -> None:
    patched: list[str] = []

    try:
        from bling_app_zero.core import bling_v3_product_client as v3
        original = getattr(v3, '_blingfix_original_image_links', None)
        if original is None:
            original = v3._image_links
            setattr(v3, '_blingfix_original_image_links', original)

        def image_links_limited(payload: dict[str, Any]) -> list[str]:
            return list(original(payload))[:MAX_BLING_IMAGES_PER_PRODUCT]

        v3._image_links = image_links_limited
        patched.append('bling_v3_product_client._image_links')
    except Exception as exc:
        add_audit_event('bling_image_preview_patch_failed', area='BLING_ENVIO', status='AVISO', details={'target': 'bling_v3_product_client', 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    try:
        from bling_app_zero.core import bling_force_product_update as force_update
        original = getattr(force_update, '_blingfix_original_image_links', None)
        if original is None:
            original = force_update._image_links
            setattr(force_update, '_blingfix_original_image_links', original)

        def force_image_links_limited(payload: dict[str, Any]) -> list[str]:
            return list(original(payload))[:MAX_BLING_IMAGES_PER_PRODUCT]

        force_update._image_links = force_image_links_limited
        patched.append('bling_force_product_update._image_links')
    except Exception as exc:
        add_audit_event('bling_image_preview_patch_failed', area='BLING_ENVIO', status='AVISO', details={'target': 'bling_force_product_update', 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    patched.append('bling_direct_sender_native_safe_layer_no_payload_patch')

    try:
        from bling_app_zero.core import bling_autocadastro_api as autocadastro
        original_media = getattr(autocadastro, '_blingfix_original_media_engine', None)
        if original_media is None:
            original_media = autocadastro._media_engine
            setattr(autocadastro, '_blingfix_original_media_engine', original_media)

        def media_engine_limited(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return _sanitize_any_bling_payload(original_media(*args, **kwargs))

        autocadastro._media_engine = media_engine_limited
        patched.append('bling_autocadastro_api._media_engine')
    except Exception as exc:
        add_audit_event('bling_image_preview_patch_failed', area='BLING_ENVIO', status='AVISO', details={'target': 'bling_autocadastro_api', 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    add_audit_event('bling_image_preview_payload_patches_installed', area='BLING_ENVIO', status='OK', details={'patched': patched, 'max_images_per_product': MAX_BLING_IMAGES_PER_PRODUCT, 'direct_sender_payload_patch_removed': True, 'responsible_file': RESPONSIBLE_FILE})


def _normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'produtos', 'produto', 'cadastrar', 'cadastro de produtos'}:
        return 'cadastro'
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'saldo'}:
        return 'estoque'
    if text in {'atualizacao_preco', 'atualização de preço', 'preco', 'preço'}:
        return 'atualizacao_preco'
    return text


def install_blingfix_runtime_patches() -> None:
    if st.session_state.get(_PATCH_INSTALLED_KEY):
        return
    _patch_bling_image_limit_guard()
    _patch_internal_image_payload_previews()
    _patch_oauth_callback()
    _patch_disconnect()
    _patch_site_operation_guard()
    _patch_stock_site_origin_filter()
    _patch_api_batch_operation_guard()
    _patch_unified_site_api_runtime_guard()
    st.session_state[_PATCH_INSTALLED_KEY] = True
    add_audit_event('blingfix_runtime_patches_installed', area='APP', status='OK', details={'logout_guard_active': logout_guard_active(), 'api_operation_guard': True, 'stock_api_origin_url_filter_patch': True, 'unified_site_api_runtime_guard_v8': True, 'bling_image_limit_guard': True, 'max_images_per_product': MAX_BLING_IMAGES_PER_PRODUCT, 'request_wrapper_accepts_args': True, 'preview_payload_patches': True, 'direct_sender_payload_patch_removed': True, 'home_wizard_navigation_native': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_blingfix_runtime_patches']
