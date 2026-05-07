from __future__ import annotations

import re
from typing import Any

VALID_GTIN_LENGTHS = {8, 12, 13, 14}


def only_digits(value: Any) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def clean_gtin(value: Any) -> str:
    digits = only_digits(value)
    if len(digits) in VALID_GTIN_LENGTHS:
        return digits
    return ''


def looks_like_gtin_column(name: Any) -> bool:
    key = str(name or '').lower()
    return any(token in key for token in ['gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'])
