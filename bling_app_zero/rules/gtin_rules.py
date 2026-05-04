from __future__ import annotations

import re
from typing import Any

VALID_GTIN_LENGTHS = {8, 12, 13, 14}


def only_digits(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\D+", "", text)


def is_valid_gtin(value: Any) -> bool:
    digits = only_digits(value)
    return len(digits) in VALID_GTIN_LENGTHS


def clean_gtin(value: Any) -> str:
    digits = only_digits(value)
    return digits if len(digits) in VALID_GTIN_LENGTHS else ""
