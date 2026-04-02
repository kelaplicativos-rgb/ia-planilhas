import re


def validar_gtin(gtin: str) -> str:
    if not gtin:
        return ""

    gtin = re.sub(r"\D", "", str(gtin))

    # tamanhos válidos
    if len(gtin) not in [8, 12, 13, 14]:
        return ""

    # prefixos inválidos comuns (China fake, etc)
    prefixos_invalidos = ["000", "111", "222", "333", "444", "555", "666", "777", "888", "999"]

    for p in prefixos_invalidos:
        if gtin.startswith(p):
            return ""

    return gtin
