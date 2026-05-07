from __future__ import annotations

import re
import unicodedata
from typing import Any


def to_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).replace('\ufeff', '').replace('\x00', '').strip()


def normalize_key(value: Any) -> str:
    text = to_text(value).lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def clean_cell(value: Any) -> str:
    text = to_text(value)
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def contains_any(value: Any, terms: list[str]) -> bool:
    key = normalize_key(value)
    return any(normalize_key(term) in key for term in terms)
