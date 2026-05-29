from __future__ import annotations

MAX_WORKERS = 8
SLOW_LINK_SECONDS = 6.0
SMART_COMPLETE_TARGET = 180
SMART_STOP_MIN_PROCESSED = 120
SMART_STOP_COMPLETE_RATIO = 0.72
SMART_STOP_NO_GAIN_WINDOW = 80
SMART_STOP_MIN_FOUND = 60
DEVTOOLS_FALLBACK_MAX_PER_RUN = 12

# BLINGFIX: limites duros para evitar travamento no Streamlit Cloud.
# A UI pode esconder campos ou enviar valores altos, mas o motor nunca deve
# aceitar varredura infinita em uma execução síncrona.
SAFE_CAPTURE_MAX_PAGES = 80
SAFE_CAPTURE_MAX_PRODUCTS = 100
SAFE_CAPTURE_MAX_DEPTH = 2
SAFE_CAPTURE_TIMEOUT_SECONDS = 75

DEEP_CAPTURE_MAX_PAGES = 250
DEEP_CAPTURE_MAX_PRODUCTS = 300
DEEP_CAPTURE_MAX_DEPTH = 3
DEEP_CAPTURE_TIMEOUT_SECONDS = 120

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
    """Normaliza limites de captura por site com teto duro.

    Nunca deixe o app receber 1_000_000 páginas/produtos em execução normal.
    Isso derruba a captura no Streamlit Cloud e retorna DataFrame vazio.
    """
    normalized_mode = str(mode or 'safe').strip().lower()
    if normalized_mode in {'deep', 'deep_site_search', 'full_deep_scan'}:
        return {
            'max_pages': _clamp_int(max_pages, DEEP_CAPTURE_MAX_PAGES, 1, DEEP_CAPTURE_MAX_PAGES),
            'max_products': _clamp_int(max_products, DEEP_CAPTURE_MAX_PRODUCTS, 1, DEEP_CAPTURE_MAX_PRODUCTS),
            'max_depth': _clamp_int(max_depth, DEEP_CAPTURE_MAX_DEPTH, 0, DEEP_CAPTURE_MAX_DEPTH),
            'timeout_seconds': DEEP_CAPTURE_TIMEOUT_SECONDS,
        }

    return {
        'max_pages': _clamp_int(max_pages, SAFE_CAPTURE_MAX_PAGES, 1, SAFE_CAPTURE_MAX_PAGES),
        'max_products': _clamp_int(max_products, SAFE_CAPTURE_MAX_PRODUCTS, 1, SAFE_CAPTURE_MAX_PRODUCTS),
        'max_depth': _clamp_int(max_depth, SAFE_CAPTURE_MAX_DEPTH, 0, SAFE_CAPTURE_MAX_DEPTH),
        'timeout_seconds': SAFE_CAPTURE_TIMEOUT_SECONDS,
    }


__all__ = [
    'DEEP_CAPTURE_MAX_DEPTH',
    'DEEP_CAPTURE_MAX_PAGES',
    'DEEP_CAPTURE_MAX_PRODUCTS',
    'DEEP_CAPTURE_TIMEOUT_SECONDS',
    'DESCRIPTION_TRIGGER_KINDS',
    'DEVTOOLS_FALLBACK_MAX_PER_RUN',
    'MAX_WORKERS',
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
    'normalize_capture_limits',
]
