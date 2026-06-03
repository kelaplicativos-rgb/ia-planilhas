from __future__ import annotations

MAX_WORKERS = 6
SLOW_LINK_SECONDS = 6.0
SMART_COMPLETE_TARGET = 180
SMART_STOP_MIN_PROCESSED = 120
SMART_STOP_COMPLETE_RATIO = 0.72
SMART_STOP_NO_GAIN_WINDOW = 80
SMART_STOP_MIN_FOUND = 60
DEVTOOLS_FALLBACK_MAX_PER_RUN = 8

SAFE_CAPTURE_MAX_PAGES = 120
SAFE_CAPTURE_MAX_PRODUCTS = 500
SAFE_CAPTURE_MAX_DEPTH = 2
SAFE_CAPTURE_TIMEOUT_SECONDS = 75

DEEP_CAPTURE_MAX_PAGES = 450
DEEP_CAPTURE_MAX_PRODUCTS = 1200
DEEP_CAPTURE_MAX_DEPTH = 3
DEEP_CAPTURE_TIMEOUT_SECONDS = 110

FLOW_CAPTURE_MAX_PAGES = 650
FLOW_CAPTURE_MAX_PRODUCTS = 1500
FLOW_CAPTURE_MAX_DEPTH = 3
FLOW_CAPTURE_TIMEOUT_SECONDS = 95

STREAMLIT_HARD_BUDGET_SECONDS = 95

# BLINGFIX 2026-06-03:
# O diagnóstico mostrou pausa técnica com 250 links encontrados e 0 linhas salvas.
# 28s/24s era pouco para Mega Center: descobria URLs, mas não dava tempo de preparar linhas.
DISCOVERY_BUDGET_SECONDS = 55
PRODUCT_READ_BUDGET_SECONDS = 58

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
    """Normaliza limites de captura por site.

    Regra BLINGFIX:
    - nenhum modo pode entregar números gigantes ao Streamlit;
    - estoque/site completo roda em lotes seguros;
    - o sistema deve retornar parcial em vez de cair por timeout.
    """
    normalized_mode = str(mode or 'safe').strip().lower()
    if normalized_mode in {'flow', 'continuous', 'stock_flow', 'estoque_flow', 'stock_balance_flow'}:
        return {
            'max_pages': _clamp_int(max_pages, FLOW_CAPTURE_MAX_PAGES, 1, FLOW_CAPTURE_MAX_PAGES),
            'max_products': _clamp_int(max_products, FLOW_CAPTURE_MAX_PRODUCTS, 1, FLOW_CAPTURE_MAX_PRODUCTS),
            'max_depth': _clamp_int(max_depth, FLOW_CAPTURE_MAX_DEPTH, 0, FLOW_CAPTURE_MAX_DEPTH),
            'timeout_seconds': FLOW_CAPTURE_TIMEOUT_SECONDS,
            'safe_limited': True,
            'flow_mode': True,
        }

    if normalized_mode in {'deep', 'deep_site_search', 'full_deep_scan'}:
        return {
            'max_pages': _clamp_int(max_pages, DEEP_CAPTURE_MAX_PAGES, 1, DEEP_CAPTURE_MAX_PAGES),
            'max_products': _clamp_int(max_products, DEEP_CAPTURE_MAX_PRODUCTS, 1, DEEP_CAPTURE_MAX_PRODUCTS),
            'max_depth': _clamp_int(max_depth, DEEP_CAPTURE_MAX_DEPTH, 0, DEEP_CAPTURE_MAX_DEPTH),
            'timeout_seconds': DEEP_CAPTURE_TIMEOUT_SECONDS,
            'safe_limited': True,
            'flow_mode': False,
        }

    return {
        'max_pages': _clamp_int(max_pages, SAFE_CAPTURE_MAX_PAGES, 1, SAFE_CAPTURE_MAX_PAGES),
        'max_products': _clamp_int(max_products, SAFE_CAPTURE_MAX_PRODUCTS, 1, SAFE_CAPTURE_MAX_PRODUCTS),
        'max_depth': _clamp_int(max_depth, SAFE_CAPTURE_MAX_DEPTH, 0, SAFE_CAPTURE_MAX_DEPTH),
        'timeout_seconds': SAFE_CAPTURE_TIMEOUT_SECONDS,
        'safe_limited': True,
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
    'SLOW_LINK_SECONDS',
    'SMART_COMPLETE_TARGET',
    'SMART_STOP_COMPLETE_RATIO',
    'SMART_STOP_MIN_FOUND',
    'SMART_STOP_MIN_PROCESSED',
    'SMART_STOP_NO_GAIN_WINDOW',
    'STREAMLIT_HARD_BUDGET_SECONDS',
    'normalize_capture_limits',
]
