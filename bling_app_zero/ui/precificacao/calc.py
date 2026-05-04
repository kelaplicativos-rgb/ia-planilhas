from __future__ import annotations

import re
from typing import Any


def norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace("R$", "").replace("r$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text)
    except Exception:
        return 0.0


def fmt_brl(value: float) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def fmt_planilha(value: float) -> str:
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def calcular_preco(custo: Any, valores: dict[str, float]) -> float:
    custo_total = (
        to_float(custo)
        + to_float(valores.get("custo_fixo"))
        + to_float(valores.get("frete_fixo"))
        + to_float(valores.get("embalagem_fixa"))
        + to_float(valores.get("despesa_fixa"))
        + to_float(valores.get("taxa_extra"))
    )
    percentual = (
        to_float(valores.get("comissao_percent"))
        + to_float(valores.get("cartao_percent"))
        + to_float(valores.get("impostos_percent"))
        + to_float(valores.get("lucro_percent"))
        + to_float(valores.get("outros_percent"))
    ) / 100.0
    divisor = 1.0 - percentual
    if divisor <= 0:
        return 0.0
    return round(custo_total / divisor, 2)
