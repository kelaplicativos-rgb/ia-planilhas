
from __future__ import annotations

import re
from typing import Any


def to_float_brasil(valor: Any, default: float = 0.0) -> float:
    if valor is None:
        return default

    texto = str(valor).strip()
    if not texto:
        return default

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return default


def formatar_numero_bling(valor: Any) -> str:
    numero = to_float_brasil(valor, 0.0)
    return f"{numero:.2f}".replace(".", ",")


def formatar_inteiro_seguro(valor: Any, default: int = 0) -> int:
    try:
        numero = to_float_brasil(valor, float(default))
        return int(round(numero))
    except Exception:
        return default
