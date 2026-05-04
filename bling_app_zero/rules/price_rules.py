from __future__ import annotations

from typing import Any


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return default
    text = text.replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def choose_price(preco_calculado: Any = None, preco_origem: Any = None, default: float = 0.0) -> float:
    calculado = to_float(preco_calculado, default=0.0)
    if calculado > 0:
        return calculado
    origem = to_float(preco_origem, default=0.0)
    if origem > 0:
        return origem
    return default
