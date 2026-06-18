from __future__ import annotations

MAX_WORKERS = 6
SLOW_LINK_SECONDS = 5.0
SMART_COMPLETE_TARGET = 120
SMART_STOP_MIN_PROCESSED = 60
SMART_STOP_COMPLETE_RATIO = 0.70
SMART_STOP_NO_GAIN_WINDOW = 40
SMART_STOP_MIN_FOUND = 40
DEVTOOLS_FALLBACK_MAX_PER_RUN = 8
SITE_ENRICH_MAX_ROWS = 3000
SITE_ENRICH_WORKERS = 8
SITE_PLAYWRIGHT_FALLBACK_MAX = 12

SAFE_CAPTURE_MAX_PAGES = 500
SAFE_CAPTURE_MAX_PRODUCTS = 3000
SAFE_CAPTURE_MAX_DEPTH = 2
SAFE_CAPTURE_TIMEOUT_SECONDS = 240

DEEP_CAPTURE_MAX_PAGES = 500
DEEP_CAPTURE_MAX_PRODUCTS = 3000
DEEP_CAPTURE_MAX_DEPTH = 2
DEEP_CAPTURE_TIMEOUT_SECONDS = 300

FLOW_CAPTURE_MAX_PAGES = 500
FLOW_CAPTURE_MAX_PRODUCTS = 3000
FLOW_CAPTURE_MAX_DEPTH = 2
FLOW_CAPTURE_TIMEOUT_SECONDS = 300

# BLINGFIX SITE 2026-06-18:
# O diagnóstico mostrou que catálogos reais podem passar de 1200 itens
# (ex.: 2699 produtos). O limite antigo cortava a origem antes da leitura.
# Mantemos um teto técnico para proteger o Streamlit, mas ele agora cobre
# catálogos médios inteiros e preserva URL de produto mesmo quando a página
# individual ainda precisa de reforço/retomada.
STREAMLIT_HARD_BUDGET_SECONDS = 330
DISCOVERY_BUDGET_SECONDS = 120
PRODUCT_READ_BUDGET_SECONDS = 260

RICH_DESCRIPTION_KINDS = {'descricao_complementar', 'ficha_tecnica', 'caracteristicas'}
DESCRIPTION_TRIGGER_KINDS = {'descricao', 'descricao_curta', 'nome_apoio', *RICH_DESCRIPTION_KINDS}

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/runner.py'


def _clamp_int(value: int | None, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value if value is not None else fallback)
    except Exception:
        number = fallback
    return max(minimum, min(maximum, number))


def normalize_capture_limits(
    *,
    max_pages: int | None = None,
    max_products: int | None = None,
    max_depth: int | None = None,
    mode: str = 'safe',
) -> dict[str, int | bool]:
    normalized_mode = str(mode or 'safe').strip().lower()
    if normalized_mode in {'flow', 'continuous', 'stock_flow', 'estoque_flow', 'stock_balance_flow'}:
        return {
            'max_pages': _clamp_int(max_pages, FLOW_CAPTURE_MAX_PAGES, 1, FLOW_CAPTURE_MAX_PAGES),
            'max_products': _clamp_int(max_products, FLOW_CAPTURE_MAX_PRODUCTS, 1, FLOW_CAPTURE_MAX_PRODUCTS),
            'max_depth': _clamp_int(max_depth, FLOW_CAPTURE_MAX_DEPTH, 0, FLOW_CAPTURE_MAX_DEPTH),
            'timeout_seconds': FLOW_CAPTURE_TIMEOUT_SECONDS,
            'safe_limited': False,
            'flow_mode': True,
        }

    if normalized_mode in {'deep', 'deep_site_search', 'full_deep_scan', 'complete', 'all_products'}:
        return {
            'max_pages': _clamp_int(max_pages, DEEP_CAPTURE_MAX_PAGES, 1, DEEP_CAPTURE_MAX_PAGES),
            'max_products': _clamp_int(max_products, DEEP_CAPTURE_MAX_PRODUCTS, 1, DEEP_CAPTURE_MAX_PRODUCTS),
            'max_depth': _clamp_int(max_depth, DEEP_CAPTURE_MAX_DEPTH, 0, DEEP_CAPTURE_MAX_DEPTH),
            'timeout_seconds': DEEP_CAPTURE_TIMEOUT_SECONDS,
            'safe_limited': False,
            'flow_mode': False,
        }

    return {
        'max_pages': _clamp_int(max_pages, SAFE_CAPTURE_MAX_PAGES, 1, SAFE_CAPTURE_MAX_PAGES),
        'max_products': _clamp_int(max_products, SAFE_CAPTURE_MAX_PRODUCTS, 1, SAFE_CAPTURE_MAX_PRODUCTS),
        'max_depth': _clamp_int(max_depth, SAFE_CAPTURE_MAX_DEPTH, 0, SAFE_CAPTURE_MAX_DEPTH),
        'timeout_seconds': SAFE_CAPTURE_TIMEOUT_SECONDS,
        'safe_limited': False,
        'flow_mode': False,
    }


__all__ = [
    'DEEP_CAPTURE_MAX_DEPTH',
    'DEEP_CAPTURE_MAX_PAGES',
    'DEEP_CAPTURE_MAX_PRODUCTS',
    'DEEP_CAPTURE_TIMEOUT_SECONDS',
    'DESCRIPTION_TRIGGER_KINDS',
    'DEVTOOLS_FALLBACK_MAX_PER_RUN',
    'DISCOVERY_BUDGET_SECONDS',
    'FLOW_CAPTURE_MAX_DEPTH',
    'FLOW_CAPTURE_MAX_PAGES',
    'FLOW_CAPTURE_MAX_PRODUCTS',
    'FLOW_CAPTURE_TIMEOUT_SECONDS',
    'MAX_WORKERS',
    'PRODUCT_READ_BUDGET_SECONDS',
    'RESPONSIBLE_FILE',
    'RICH_DESCRIPTION_KINDS',
    'SAFE_CAPTURE_MAX_DEPTH',
    'SAFE_CAPTURE_MAX_PAGES',
    'SAFE_CAPTURE_MAX_PRODUCTS',
    'SAFE_CAPTURE_TIMEOUT_SECONDS',
    'SITE_ENRICH_MAX_ROWS',
    'SITE_ENRICH_WORKERS',
    'SITE_PLAYWRIGHT_FALLBACK_MAX',
    'SLOW_LINK_SECONDS',
    'SMART_COMPLETE_TARGET',
    'SMART_STOP_COMPLETE_RATIO',
    'SMART_STOP_MIN_FOUND',
    'SMART_STOP_MIN_PROCESSED',
    'SMART_STOP_NO_GAIN_WINDOW',
    'STREAMLIT_HARD_BUDGET_SECONDS',
    'normalize_capture_limits',
]
