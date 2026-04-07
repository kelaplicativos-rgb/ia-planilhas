from __future__ import annotations

import math
import re
from typing import Any


def normalize_value(value: Any) -> str | None:
    try:
        if value is None:
            return None

        texto = str(value).strip()

        if texto == "":
            return None

        if texto.lower() in {"nan", "none", "null", "<na>"}:
            return None

        return texto
    except Exception:
        return None


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            numero = float(value)
            if math.isnan(numero) or math.isinf(numero):
                return None
            return numero

        texto = str(value).strip()

        if texto == "":
            return None

        texto_lower = texto.lower()
        if texto_lower in {
            "nan",
            "none",
            "null",
            "<na>",
            "inf",
            "-inf",
            "infinity",
            "-infinity",
        }:
            return None

        texto = (
            texto.replace("R$", "")
            .replace("\u00a0", "")
            .replace(" ", "")
            .strip()
        )

        # Mantém apenas dígitos, separadores e sinal.
        texto = re.sub(r"[^0-9,.\-]", "", texto)

        if texto in {"", "-", ".", ",", "-.", "-,"}:
            return None

        # Casos:
        # 1) 1.234,56  -> milhar '.' e decimal ','
        # 2) 1,234.56  -> milhar ',' e decimal '.'
        # 3) 1234,56   -> decimal ','
        # 4) 1234.56   -> decimal '.'
        if "," in texto and "." in texto:
            ultimo_ponto = texto.rfind(".")
            ultima_virgula = texto.rfind(",")

            if ultima_virgula > ultimo_ponto:
                # Formato brasileiro: 1.234,56
                texto = texto.replace(".", "")
                texto = texto.replace(",", ".")
            else:
                # Formato internacional: 1,234.56
                texto = texto.replace(",", "")
        elif "," in texto:
            # Apenas vírgula: decide se é decimal ou separador de milhar
            if texto.count(",") > 1:
                partes = texto.split(",")
                if len(partes[-1]) in {1, 2}:
                    texto = "".join(partes[:-1]) + "." + partes[-1]
                else:
                    texto = "".join(partes)
            else:
                texto = texto.replace(",", ".")
        elif "." in texto:
            # Apenas ponto: decide se é decimal ou separador de milhar
            if texto.count(".") > 1:
                partes = texto.split(".")
                if len(partes[-1]) in {1, 2}:
                    texto = "".join(partes[:-1]) + "." + partes[-1]
                else:
                    texto = "".join(partes)

        numero = float(texto)
        if math.isnan(numero) or math.isinf(numero):
            return None
        return numero
    except Exception:
        return None


def format_money(value: Any) -> str:
    try:
        numero = safe_float(value)
        if numero is None:
            numero = 0.0

        return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


__all__ = [
    "normalize_value",
    "safe_float",
    "format_money",
]
