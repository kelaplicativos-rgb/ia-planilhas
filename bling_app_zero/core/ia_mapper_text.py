# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from typing import Any, Set

from .ia_mapper_config import IMAGE_KEYWORDS


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"[_/\\\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s\(\)]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simplify_token_set(text: str) -> Set[str]:
    return set(normalize_text(text).split())


def is_image_like(text: str) -> bool:
    tokens = simplify_token_set(text)
    return bool(tokens.intersection(IMAGE_KEYWORDS))
