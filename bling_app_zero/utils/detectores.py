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
    texto = limpar_texto(valor)
    if not texto:
        return False

    texto_limpo = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto_limpo:
        return False

    try:
        normalizado = texto_limpo

        if "," in normalizado and "." in normalizado:
            if normalizado.rfind(",") > normalizado.rfind("."):
                normalizado = normalizado.replace(".", "").replace(",", ".")
            else:
                normalizado = normalizado.replace(",", "")
        else:
            if "," in normalizado:
                normalizado = normalizado.replace(".", "").replace(",", ".")

        normalizado = re.sub(r"[^0-9.\-]", "", normalizado)
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
    texto = limpar_texto(valor).lower()
    if not texto:
        return False

    return (
        texto.startswith("http://")
        or texto.startswith("https://")
        or texto.startswith("www.")
    )


# =========================================================
# DETECÇÃO DE DATA
# =========================================================
def parece_data(valor: Any) -> bool:
    """
    Verifica se o valor parece uma data nos formatos mais comuns.
    """
    texto = limpar_texto(valor)
    if not texto:
        return False

    padroes = [
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{2}-\d{2}-\d{4}$",
    ]

    return any(re.match(padrao, texto) for padrao in padroes)


# =========================================================
# DETECÇÃO DE GTIN / EAN
# =========================================================
def parece_gtin(valor: Any) -> bool:
    """
    Verifica se o valor parece um GTIN/EAN
    com base no tamanho dos dígitos.
    """
    digitos = somente_digitos(valor)
    return len(digitos) in {8, 12, 13, 14}


# =========================================================
# DETECÇÃO DE NCM
# =========================================================
def parece_ncm(valor: Any) -> bool:
    """
    Verifica se o valor parece um NCM válido
    pelo tamanho de 8 dígitos.
    """
    digitos = somente_digitos(valor)
    return len(digitos) == 8


# =========================================================
# DETECÇÃO DE CEST
# =========================================================
def parece_cest(valor: Any) -> bool:
    """
    Verifica se o valor parece um CEST válido
    pelo tamanho de 7 dígitos.
    """
    digitos = somente_digitos(valor)
    return len(digitos) == 7


# =========================================================
# DETECÇÃO DE VALOR SIM/NÃO
# =========================================================
def parece_sim_nao(valor: Any) -> bool:
    """
    Verifica se o valor parece um campo binário simples.
    """
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
    }

    return texto in validos
