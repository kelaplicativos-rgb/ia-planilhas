from __future__ import annotations

import re
from typing import Any

from bling_app_zero.utils.limpeza import limpar_texto, somente_digitos


# =========================================================
# DETECÇÃO DE NÚMERO
# =========================================================
def parece_numero(valor: Any) -> bool:
    """
    Verifica se um valor parece numérico.
    Aceita formatos como:
    - 10
    - 10,50
    - 1.250,99
    - R$ 99,90
    - 15%
    """
    try:
        texto = limpar_texto(valor)
        if not texto:
            return False

        texto_limpo = re.sub(r"[^0-9,.\-]", "", texto)
        if not texto_limpo:
            return False

        normalizado = texto_limpo

        if "," in normalizado and "." in normalizado:
            if normalizado.rfind(",") > normalizado.rfind("."):
                normalizado = normalizado.replace(".", "").replace(",", ".")
            else:
                normalizado = normalizado.replace(",", "")
        else:
            if "," in normalizado:
                normalizado = normalizado.replace(".", "").replace(",", ".")
            elif normalizado.count(".") > 1:
                partes = normalizado.split(".")
                if len(partes[-1]) in {1, 2}:
                    normalizado = "".join(partes[:-1]) + "." + partes[-1]
                else:
                    normalizado = "".join(partes)

        normalizado = re.sub(r"[^0-9.\-]", "", normalizado)

        if normalizado in {"", "-", ".", "-."}:
            return False

        float(normalizado)
        return True
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE URL
# =========================================================
def parece_url(valor: Any) -> bool:
    """
    Verifica se o valor parece uma URL.
    """
    try:
        texto = limpar_texto(valor).lower()
        if not texto:
            return False

        if (
            texto.startswith("http://")
            or texto.startswith("https://")
            or texto.startswith("www.")
        ):
            return True

        # Domínio simples sem protocolo
        return bool(re.match(r"^[a-z0-9][a-z0-9\-._]*\.[a-z]{2,}(/.*)?$", texto))
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE DATA
# =========================================================
def parece_data(valor: Any) -> bool:
    """
    Verifica se o valor parece uma data nos formatos mais comuns.
    """
    try:
        texto = limpar_texto(valor)
        if not texto:
            return False

        padroes = [
            r"^\d{2}/\d{2}/\d{4}$",
            r"^\d{4}-\d{2}-\d{2}$",
            r"^\d{2}-\d{2}-\d{4}$",
            r"^\d{2}/\d{2}/\d{2}$",
        ]

        return any(re.match(padrao, texto) for padrao in padroes)
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE GTIN / EAN
# =========================================================
def parece_gtin(valor: Any) -> bool:
    """
    Verifica se o valor parece um GTIN/EAN
    com base no tamanho dos dígitos.
    """
    try:
        digitos = somente_digitos(valor)
        return len(digitos) in {8, 12, 13, 14}
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE NCM
# =========================================================
def parece_ncm(valor: Any) -> bool:
    """
    Verifica se o valor parece um NCM válido
    pelo tamanho de 8 dígitos.
    """
    try:
        digitos = somente_digitos(valor)
        return len(digitos) == 8
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE CEST
# =========================================================
def parece_cest(valor: Any) -> bool:
    """
    Verifica se o valor parece um CEST válido
    pelo tamanho de 7 dígitos.
    """
    try:
        digitos = somente_digitos(valor)
        return len(digitos) == 7
    except Exception:
        return False


# =========================================================
# DETECÇÃO DE VALOR SIM/NÃO
# =========================================================
def parece_sim_nao(valor: Any) -> bool:
    """
    Verifica se o valor parece um campo binário simples.
    """
    try:
        texto = limpar_texto(valor).lower()
        if not texto:
            return False

        validos = {
            "sim",
            "nao",
            "não",
            "s",
            "n",
            "true",
            "false",
            "ativo",
            "inativo",
            "1",
            "0",
            "yes",
            "no",
        }

        return texto in validos
    except Exception:
        return False


__all__ = [
    "parece_numero",
    "parece_url",
    "parece_data",
    "parece_gtin",
    "parece_ncm",
    "parece_cest",
    "parece_sim_nao",
]
