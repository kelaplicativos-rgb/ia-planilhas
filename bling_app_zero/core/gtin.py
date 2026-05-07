from __future__ import annotations

import re
from typing import Any

VALID_GTIN_LENGTHS = {8, 12, 13, 14}
INVALID_GS1_PREFIXES = {'020', '040', '200', '201', '202', '203', '204', '205', '206', '207', '208', '209', '687'}


def only_digits(value: Any) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _has_valid_length(digits: str) -> bool:
    return len(digits) in VALID_GTIN_LENGTHS


def _has_valid_checksum(digits: str) -> bool:
    if not _has_valid_length(digits):
        return False

    body = digits[:-1]
    expected = int(digits[-1])
    total = 0
    reversed_body = list(map(int, reversed(body)))

    for index, number in enumerate(reversed_body):
        total += number * (3 if index % 2 == 0 else 1)

    calculated = (10 - (total % 10)) % 10
    return calculated == expected


def _has_valid_gs1_prefix(digits: str) -> bool:
    if not digits or len(digits) < 3:
        return False

    prefix3 = digits[:3]
    if prefix3 in INVALID_GS1_PREFIXES:
        return False

    if digits == '0' * len(digits):
        return False

    return True


def is_valid_gtin(value: Any) -> bool:
    digits = only_digits(value)
    return _has_valid_length(digits) and _has_valid_gs1_prefix(digits) and _has_valid_checksum(digits)


def clean_gtin(value: Any) -> str:
    digits = only_digits(value)
    if is_valid_gtin(digits):
        return digits
    return ''


def looks_like_gtin_column(name: Any) -> bool:
    key = str(name or '').lower()
    return any(token in key for token in ['gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'])
