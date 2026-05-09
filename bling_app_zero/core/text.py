from __future__ import annotations

import re
import unicodedata
from typing import Any

MOJIBAKE_REPLACEMENTS = {
    'Ã¡': 'á', 'Ã ': 'à', 'Ã¢': 'â', 'Ã£': 'ã', 'Ã¤': 'ä',
    'Ã©': 'é', 'Ãª': 'ê', 'Ã¨': 'è',
    'Ã­': 'í', 'Ã¬': 'ì',
    'Ã³': 'ó', 'Ã´': 'ô', 'Ãµ': 'õ', 'Ã²': 'ò',
    'Ãº': 'ú', 'Ã¼': 'ü', 'Ã¹': 'ù',
    'Ã§': 'ç',
    'Ã‰': 'É', 'Ã“': 'Ó', 'Ã‡': 'Ç',
    'Âº': 'º', 'Âª': 'ª', 'Â®': '®', 'Â©': '©', 'Â': '',
    'â€“': '–', 'â€”': '—', 'â€˜': '‘', 'â€™': '’', 'â€œ': '“', 'â€': '”',
    '�': '',
}


def to_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    text = text.replace('\ufeff', '').replace('\x00', '')
    return text.strip()


def fix_mojibake(value: Any) -> str:
    text = to_text(value)
    if not text:
        return ''
    for wrong, right in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(wrong, right)
    return text


def normalize_key(value: Any) -> str:
    text = fix_mojibake(value).lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def clean_cell(value: Any) -> str:
    text = fix_mojibake(value)
    text = text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def contains_any(value: Any, terms: list[str]) -> bool:
    key = normalize_key(value)
    return any(normalize_key(term) in key for term in terms)
