import re
from typing import Any

from bling_app_zero.utils.limpeza import limpar_texto


# =========================================================
# NORMALIZAÇÃO DE VALOR NUMÉRICO
# =========================================================
def normalizar_valor_numerico(valor: Any) -> float:
    """
    Converte diferentes formatos numéricos para float.

    Exemplos aceitos:
    - 10
    - 10.5
    - 10,5
    - 1.250,99
    - 1250.99
    - R$ 99,90
    - 15%
    """
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    texto = limpar_texto(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace("%", "").strip()

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    else:
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


# =========================================================
# FORMATAÇÃO BRASILEIRA
# =========================================================
def formatar_numero_brasileiro(valor: Any, casas_decimais: int = 2) -> str:
    """
    Formata número no padrão brasileiro.
    Exemplo:
    1234.5 -> 1234,50
    """
    try:
        numero = float(valor)
    except Exception:
        numero = 0.0

    formato = f"{{:.{casas_decimais}f}}"
    return formato.format(numero).replace(".", ",")


# =========================================================
# VERIFICA SE É ZERO OU VAZIO
# =========================================================
def numero_zerado_ou_vazio(valor: Any) -> bool:
    """
    Retorna True se o valor estiver vazio ou resultar em zero.
    """
    texto = limpar_texto(valor)
    if not texto:
        return True

    return normalizar_valor_numerico(valor) == 0.0


# =========================================================
# CONVERTE PARA PERCENTUAL DECIMAL
# =========================================================
def percentual_para_decimal(valor: Any) -> float:
    """
    Converte percentual informado pelo usuário para decimal.
    Exemplos:
    15 -> 0.15
    "15%" -> 0.15
    "15,5" -> 0.155
    """
    numero = normalizar_valor_numerico(valor)
    return numero / 100.0


# =========================================================
# ARREDONDAMENTO SEGURO
# =========================================================
def arredondar_moeda(valor: Any, casas_decimais: int = 2) -> float:
    """
    Arredonda valor monetário com segurança.
    """
    try:
        return round(float(valor), casas_decimais)
    except Exception:
        return 0.0
