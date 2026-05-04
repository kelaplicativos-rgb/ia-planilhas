from __future__ import annotations

from typing import Any


def normalize_stock(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text or text in {"nan", "none", "null"}:
        return default
    if any(word in text for word in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
        return 0.0
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def normalize_deposit(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text
