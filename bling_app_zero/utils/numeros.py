from typing import Any, Optional


def normalize_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    texto = str(value).strip()

    if texto == "":
        return None

    if texto.lower() in {"nan", "none", "null"}:
        return None

    return texto


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    texto = str(value).strip()
    if texto == "":
        return None

    texto = texto.replace("R$", "").replace(".", "").replace(",", ".").strip()

    try:
        return float(texto)
    except Exception:
        return None


def format_money(value: Any) -> str:
    numero = safe_float(value)
    if numero is None:
        numero = 0.0

    return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
