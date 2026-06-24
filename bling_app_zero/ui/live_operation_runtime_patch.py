from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.live_operation_progress import append_live_operation_progress, reset_live_operation_progress
from bling_app_zero.ui.live_operation_panel import render_live_operation_panel, render_live_operation_sidebar

RESPONSIBLE_FILE = 'bling_app_zero/ui/live_operation_runtime_patch.py'
_PATCH_KEY = 'live_operation_runtime_patch_installed_v1'


def _safe_int(value: object) -> int:
    try:
        if value in (None, ''):
            return 0
        return int(float(value))
    except Exception:
        return 0


def _safe_progress(processed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, float(processed) / max(total, 1)))


def _install_category_confidence_strict() -> None:
    try:
        from bling_app_zero.ui.category_confidence_strict_runtime import install
        install()
        add_audit_event(
            'live_operation_runtime_category_confidence_strict_loaded',
            area='UNIVERSAL',
            status='OK',
            details={'confidence_min': 1.0, 'slider_removed': True, 'responsible_file': RESPONSIBLE_FILE},
        )
    except Exception as exc:
        add_audit_event(
            'live_operation_runtime_category_confidence_strict_failed',
            area='UNIVERSAL',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )


def _install_universal_price_calculator() -> None:
    try:
        from bling_app_zero.ui.universal_price_calculator_patch import install
        install()
        add_audit_event(
            'live_operation_runtime_universal_price_calculator_loaded',
            area='UNIVERSAL',
            status='OK',
            details={'official_calculator': True, 'replaces': 'render_shared_calculator', 'responsible_file': RESPONSIBLE_FILE},
        )
    except Exception as exc:
        add_audit_event(
            'live_operation_runtime_universal_price_calculator_failed',
            area='UNIVERSAL',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )


def _patch_site_progress() -> None:
    try:
        from bling_app_zero.ui import site_progress
    except Exception as exc:
        add_audit_event('live_progress_site_patch_failed', area='PROGRESSO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    original_append: Callable[..., Any] | None = getattr(site_progress, '_live_original_append_site_progress', None)
    if original_append is None:
        original_append = site_progress.append_site_progress
        setattr(site_progress, '_live_original_append_site_progress', original_append)

    def append_site_progress_with_global(payload: dict | None = None) -> None:
        payload = dict(payload or {})
        original_append(payload)
        append_live_operation_progress(
            {
                'area': payload.get('area') or 'SITE',
                'operation': payload.get('operation') or st.session_state.get('flow_spine_operation') or 'site',
                'stage': payload.get('stage') or 'Busca por site',
                'message': payload.get('message') or '',
                'progress': payload.get('progress') or payload.get('progress_value') or 0.0,
                'processed': payload.get('processed') or payload.get('scanned_pages') or payload.get('deep_capture_scanned_pages') or 0,
                'total': payload.get('max_pages') or payload.get('max_products') or payload.get('total') or 0,
                'success': payload.get('found_products') or payload.get('urls_found') or payload.get('deep_capture_found_products') or payload.get('total') or 0,
                'failed': payload.get('errors') or 0,
                'skipped': payload.get('skipped') or 0,
                'current_url': payload.get('current_url') or '',
                'checkpoint': payload.get('checkpoint') or 'captura salva',
                'elapsed_seconds': payload.get('elapsed_seconds') or payload.get('total_seconds') or payload.get('discovery_seconds') or 0,
            }
        )

    original_reset: Callable[..., Any] | None = getattr(site_progress, '_live_original_reset_site_progress', None)
    if original_reset is None:
        original_reset = site_progress.reset_site_progress
        setattr(site_progress, '_live_original_reset_site_progress', original_reset)

    def reset_site_progress_with_global() -> None:
        original_reset()
        reset_live_operation_progress()

    original_live_panel: Callable[..., Any] | None = getattr(site_progress, '_live_original_render_live_site_operation_panel', None)
    if original_live_panel is None:
        original_live_panel = site_progress.render_live_site_operation_panel
        setattr(site_progress, '_live_original_render_live_site_operation_panel', original_live_panel)

    def render_live_site_operation_panel_with_global() -> None:
        original_live_panel()
        render_live_operation_panel(title='Painel vivo global', expanded_history=False)
        render_live_operation_sidebar()

    site_progress.append_site_progress = append_site_progress_with_global
    site_progress.reset_site_progress = reset_site_progress_with_global
    site_progress.render_live_site_operation_panel = render_live_site_operation_panel_with_global


def _patch_api_progress() -> None:
    try:
        from bling_app_zero.ui import bling_api_batch_panel
    except Exception as exc:
        add_audit_event('live_progress_api_patch_failed', area='PROGRESSO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    original_sync: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_live_original_sync_state', None)
    if original_sync is None:
        original_sync = bling_api_batch_panel._sync_state
        setattr(bling_api_batch_panel, '_live_original_sync_state', original_sync)

    def sync_state_with_global(state_obj):
        legacy = original_sync(state_obj)
        total = _safe_int(legacy.get('total'))
        processed = _safe_int(legacy.get('attempted') or legacy.get('offset'))
        sent = _safe_int(legacy.get('sent'))
        failed = _safe_int(legacy.get('failed'))
        skipped = _safe_int(legacy.get('skipped'))
        operation = str(legacy.get('operation') or '')
        status = 'Envio concluído' if bool(legacy.get('done')) else 'Envio inteligente no Bling'
        append_live_operation_progress(
            {
                'area': 'BLING_API',
                'operation': operation,
                'stage': status,
                'message': f'{processed}/{total} processados · {sent} enviados · {failed} falhas · {skipped} ignorados',
                'progress': _safe_progress(processed, total),
                'processed': processed,
                'total': total,
                'success': sent,
                'failed': failed,
                'skipped': skipped,
                'checkpoint': 'checkpoint salvo',
            }
        )
        return legacy

    original_render_progress: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_live_original_render_progress', None)
    if original_render_progress is None:
        original_render_progress = bling_api_batch_panel._render_progress
        setattr(bling_api_batch_panel, '_live_original_render_progress', original_render_progress)

    def render_progress_with_global(state: dict[str, Any]) -> None:
        original_render_progress(state)
        render_live_operation_panel(title='Processamento minucioso', expanded_history=False)

    bling_api_batch_panel._sync_state = sync_state_with_global
    bling_api_batch_panel._render_progress = render_progress_with_global


def _patch_universal_progress() -> None:
    try:
        from bling_app_zero.ui import universal_flow
    except Exception as exc:
        add_audit_event('live_progress_universal_patch_failed', area='PROGRESSO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    if not hasattr(universal_flow, '_progress_callback'):
        add_audit_event('live_progress_universal_callback_missing_ignored', area='PROGRESSO', status='INFO', details={'responsible_file': RESPONSIBLE_FILE})
        return

    original_callback_factory: Callable[..., Any] | None = getattr(universal_flow, '_live_original_progress_callback', None)
    if original_callback_factory is None:
        original_callback_factory = universal_flow._progress_callback
        setattr(universal_flow, '_live_original_progress_callback', original_callback_factory)

    def progress_callback_with_global(progress_bar, status_box):
        original_callback = original_callback_factory(progress_bar, status_box)

        def callback(info: dict | None = None) -> None:
            payload = dict(info or {})
            original_callback(payload)
            append_live_operation_progress(
                {
                    'area': payload.get('area') or 'UNIVERSAL',
                    'operation': payload.get('operation') or 'universal',
                    'stage': payload.get('stage') or 'Processando universal',
                    'message': payload.get('message') or '',
                    'progress': payload.get('progress') or 0.0,
                    'processed': payload.get('processed') or payload.get('rows_done') or 0,
                    'total': payload.get('total') or payload.get('rows_total') or 0,
                    'success': payload.get('success') or payload.get('found_products') or 0,
                    'failed': payload.get('failed') or payload.get('errors') or 0,
                    'skipped': payload.get('skipped') or 0,
                    'current_url': payload.get('current_url') or '',
                    'checkpoint': payload.get('checkpoint') or 'processamento universal salvo',
                }
            )

        return callback

    universal_flow._progress_callback = progress_callback_with_global


def install_live_operation_runtime_patch() -> None:
    if st.session_state.get(_PATCH_KEY):
        return
    _install_category_confidence_strict()
    _install_universal_price_calculator()
    _patch_site_progress()
    _patch_api_progress()
    _patch_universal_progress()
    st.session_state[_PATCH_KEY] = True
    add_audit_event('live_operation_runtime_patch_installed', area='PROGRESSO', status='OK', details={'site': True, 'api': True, 'universal': True, 'category_confidence_strict': True, 'official_universal_price_calculator': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_live_operation_runtime_patch']
