from __future__ import annotations

MAX_WORKERS = 8
SLOW_LINK_SECONDS = 6.0
SMART_COMPLETE_TARGET = 180
SMART_STOP_MIN_PROCESSED = 120
SMART_STOP_COMPLETE_RATIO = 0.72
SMART_STOP_NO_GAIN_WINDOW = 80
SMART_STOP_MIN_FOUND = 60
DEVTOOLS_FALLBACK_MAX_PER_RUN = 12

# Modo seguro: usado apenas quando o usuário quer uma captura menor/controlada.
SAFE_CAPTURE_MAX_PAGES = 250
SAFE_CAPTURE_MAX_PRODUCTS = 1200
SAFE_CAPTURE_MAX_DEPTH = 2
SAFE_CAPTURE_TIMEOUT_SECONDS = 120

# Modo profundo padrão: cadastro/preço/site completo sem a amostra antiga de 100 linhas.
DEEP_CAPTURE_MAX_PAGES = 3000
DEEP_CAPTURE_MAX_PRODUCTS = 20000
DEEP_CAPTURE_MAX_DEPTH = 6
DEEP_CAPTURE_TIMEOUT_SECONDS = 420

# Modo fluxo contínuo: usado principalmente para Atualizar estoque por API,
# onde o objetivo é deixar a busca fluir no site inteiro sem cair por
# "quantidade segura". Ainda existe um teto técnico alto para evitar loop infinito.
FLOW_CAPTURE_MAX_PAGES = 10000
FLOW_CAPTURE_MAX_PRODUCTS = 100000
FLOW_CAPTURE_MAX_DEPTH = 8
FLOW_CAPTURE_TIMEOUT_SECONDS = 900

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
) -> dict[str, int]:
    """Normaliza limites de captura por site.

    safe  = captura controlada.
    deep  = busca completa padrão.
    flow  = fluxo contínuo para estoque/API sem parada por quantidade segura.
    """
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

    if normalized_mode in {'deep', 'deep_site_search', 'full_deep_scan'}:
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
    'FLOW_CAPTURE_MAX_DEPTH',
    'FLOW_CAPTURE_MAX_PAGES',
    'FLOW_CAPTURE_MAX_PRODUCTS',
    'FLOW_CAPTURE_TIMEOUT_SECONDS',
    'MAX_WORKERS',
    'RESPONSIBLE_FILE',
    'RICH_DESCRIPTION_KINDS',
    'SAFE_CAPTURE_MAX_DEPTH',
    'SAFE_CAPTURE_MAX_PAGES',
    'SAFE_CAPTURE_MAX_PRODUCTS',
    'SAFE_CAPTURE_TIMEOUT_SECONDS',
    'SLOW_LINK_SECONDS',
    'SMART_COMPLETE_TARGET',
    'SMART_COMPLETE_RATIO',
    'SMART_STOP_COMPLETE_RATIO',
    'SMART_STOP_MIN_FOUND',
    'SMART_STOP_MIN_PROCESSED',
    'SMART_STOP_NO_GAIN_WINDOW',
    'normalize_capture_limits',
]
