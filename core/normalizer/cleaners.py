import re
import pandas as pd


def valor_vazio(valor):
    if valor is None:
        return True

    try:
        if pd.isna(valor):
            return True
    except Exception:
        pass

    txt = str(valor).strip().lower()
    return txt in ["", "nan", "none", "null", "nat"]


def limpar_texto(valor):
    if valor_vazio(valor):
        return ""
    return str(valor).strip()


def limpar_preco(valor):
    if valor_vazio(valor):
        return "0.01"

    txt = str(valor).strip()
    txt = txt.replace("R$", "").replace("r$", "").strip()

    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    else:
        txt = re.sub(r"[^\d.]", "", txt)

    try:
        numero = float(txt)
        if numero <= 0:
            return "0.01"
        return f"{numero:.2f}"
    except Exception:
        return "0.01"


def limpar_estoque(valor, estoque_padrao=0):
    if valor_vazio(valor):
        return int(estoque_padrao)

    txt = str(valor).strip().lower()

    if any(x in txt for x in ["sem estoque", "esgotado", "indisponível", "indisponivel"]):
        return 0

    txt = txt.replace(",", ".")
    achado = re.search(r"-?\d+(?:\.\d+)?", txt)

    if achado:
        try:
            return int(float(achado.group(0)))
        except Exception:
            return int(estoque_padrao)

    return int(estoque_padrao)


def _somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def validar_gtin(valor):
    """
    Regra segura para evitar erro no Bling:
    - aceita só 8, 12, 13 ou 14 dígitos
    - valida dígito verificador
    - se falhar, retorna vazio
    """
    if valor_vazio(valor):
        return ""

    codigo = _somente_digitos(valor)

    if len(codigo) not in [8, 12, 13, 14]:
        return ""

    try:
        digitos = [int(d) for d in codigo]
    except Exception:
        return ""

    corpo = digitos[:-1]
    verificador = digitos[-1]

    corpo_invertido = list(reversed(corpo))
    soma = 0

    for i, n in enumerate(corpo_invertido):
        if i % 2 == 0:
            soma += n * 3
        else:
            soma += n

    calculado = (10 - (soma % 10)) % 10

    if calculado != verificador:
        return ""

    return codigo
