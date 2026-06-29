from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/wbuy_capture_full_runtime.py'
WBUY_MIN_PRODUCTS_FOR_CATEGORY = 24


def _safe_int(value: object, fallback: int) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        parsed = 0
    return parsed if parsed > 0 else fallback


def install_wbuy_capture_full_runtime() -> bool:
    """Evita que categoria WBuy/Atacadum encerre com 2 ou 5 produtos.

    O diagnóstico de 2026-06-29 mostrou fluxo WBuy com produtos nomeados, porém
    apenas 2/5 linhas, enquanto as categorias públicas têm dezenas de cards.
    Como a referência do SmartScan é importada diretamente no painel, patchamos o
    agente e também o alias já carregado em ``site_panel_capture``.
    """
    try:
        from bling_app_zero.agents import site_capture_agent as agent
    except Exception as exc:
        add_audit_event(
            'wbuy_capture_full_runtime_install_failed',
            area='SITE',
            step='boot',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False

    installed_any = False

    original_reason = getattr(agent, '_wbuy_weak_capture_reason', None)
    if callable(original_reason) and not getattr(original_reason, '_wbuy_full_runtime_patch', False):
        def patched_wbuy_weak_capture_reason(df: pd.DataFrame, *, max_products: int) -> str:
            rows, named_rows = agent._wbuy_capture_stats(df)
            if rows <= 0:
                return ''
            requested = _safe_int(max_products, getattr(agent, 'SMARTSCAN_SAFE_URL_BATCH', 1200))
            min_target = min(WBUY_MIN_PRODUCTS_FOR_CATEGORY, max(WBUY_MIN_PRODUCTS_FOR_CATEGORY, requested))
            if rows < min_target:
                if named_rows == 0:
                    return f'{rows} linha(s) sem nome/descricao em captura WBuy; alvo mínimo {min_target}'
                return f'{rows} linha(s) abaixo do alvo mínimo WBuy ({min_target}); forçar leitura de cards/paginação'
            return original_reason(df, max_products=max_products)

        patched_wbuy_weak_capture_reason._wbuy_full_runtime_patch = True  # type: ignore[attr-defined]
        agent._wbuy_weak_capture_reason = patched_wbuy_weak_capture_reason
        installed_any = True

    original_run = getattr(agent, 'run_bling_smartscan', None)
    if callable(original_run) and not getattr(original_run, '_wbuy_full_runtime_patch', False):
        @wraps(original_run)
        def patched_run_bling_smartscan(*args: Any, **kwargs: Any):
            raw_urls = str(kwargs.get('raw_urls') or '')
            all_products = bool(kwargs.get('all_products'))
            current_max = _safe_int(kwargs.get('max_products'), getattr(agent, 'SMARTSCAN_SAFE_URL_BATCH', 1200))
            platform = agent.detect_site_platform(raw_urls)
            if platform.platform == 'wbuy' and all_products and current_max < WBUY_MIN_PRODUCTS_FOR_CATEGORY:
                expanded = getattr(agent, 'SMARTSCAN_SAFE_URL_BATCH', 1200)
                kwargs['max_products'] = expanded
                callback: Callable[[dict], None] | None = kwargs.get('progress_callback')
                if callback:
                    try:
                        callback({
                            'stage': 'WBuy captura completa',
                            'message': f'Limite pequeno ({current_max}) detectado em WBuy. Expandindo para ler cards/paginação pública.',
                            'progress': 0.13,
                            'platform': 'wbuy',
                            'max_products_before': current_max,
                            'max_products_after': expanded,
                            'responsible_file': RESPONSIBLE_FILE,
                        })
                    except Exception:
                        pass
                add_audit_event(
                    'blingsmartscan_wbuy_min_products_expanded',
                    area='SITE',
                    step='entrada',
                    status='OK',
                    details={
                        'all_products': all_products,
                        'max_products_before': current_max,
                        'max_products_after': expanded,
                        'platform': platform.platform,
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            return original_run(*args, **kwargs)

        patched_run_bling_smartscan._wbuy_full_runtime_patch = True  # type: ignore[attr-defined]
        agent.run_bling_smartscan = patched_run_bling_smartscan
        installed_any = True

        try:
            from bling_app_zero.ui import site_panel_capture
            site_panel_capture.run_bling_smartscan = patched_run_bling_smartscan
        except Exception:
            pass

    add_audit_event(
        'wbuy_capture_full_runtime_installed',
        area='SITE',
        step='boot',
        status='OK' if installed_any else 'INFO',
        details={
            'installed_any': installed_any,
            'min_products': WBUY_MIN_PRODUCTS_FOR_CATEGORY,
            'patches_agent_alias_and_panel_alias': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return installed_any


__all__ = ['install_wbuy_capture_full_runtime']
