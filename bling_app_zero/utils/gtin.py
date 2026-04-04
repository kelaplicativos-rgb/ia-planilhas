from typing import Any, List, Tuple

import pandas as pd

from bling_app_zero.utils.limpeza import limpar_texto, somente_digitos


# =========================================================
# LIMPEZA DE GTIN
# =========================================================
def limpar_gtin(valor: Any) -> str:
    """
    Mantém apenas os dígitos do GTIN/EAN.
    """
    return somente_digitos(valor)


# =========================================================
# VALIDAÇÃO DE CHECKSUM GTIN
# =========================================================
def validar_gtin_checksum(gtin: str) -> bool:
    """
    Valida GTIN/EAN pelos formatos:
    - EAN-8
    - UPC-A (12)
    - EAN-13
    - GTIN-14
    """
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3

    for numero in reversed(corpo):
        soma += numero * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == digito_verificador


# =========================================================
# TRATAMENTO FINAL DE GTIN
# =========================================================
def tratar_gtin(valor: Any) -> Tuple[str, bool]:
    """
    Limpa e valida o GTIN.
    Retorna:
    - GTIN limpo se válido
    - string vazia se inválido
    - bool indicando validade
    """
    gtin = limpar_gtin(valor)

    if not gtin:
        return "", False

    if validar_gtin_checksum(gtin):
        return gtin, True

    return "", False


# =========================================================
# APLICA VALIDAÇÃO EM DATAFRAME
# =========================================================
def aplicar_validacao_gtin_df(df: pd.DataFrame, coluna: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Valida a coluna de GTIN em um DataFrame.
    GTIN inválido é zerado (fica vazio) automaticamente.
    Retorna:
    - DataFrame atualizado
    - lista de logs
    """
    logs: List[str] = []

    if coluna not in df.columns:
        return df, logs

    novos_valores = []
    total_invalidos = 0
    total_validos = 0

    for idx, valor in enumerate(df[coluna].tolist(), start=1):
        texto_original = limpar_texto(valor)

        if not texto_original:
            novos_valores.append("")
            continue

        gtin_corrigido, valido = tratar_gtin(texto_original)

        if valido:
            novos_valores.append(gtin_corrigido)
            total_validos += 1
        else:
            novos_valores.append("")
            total_invalidos += 1
            logs.append(f"Linha {idx}: GTIN inválido zerado ({texto_original})")

    df[coluna] = novos_valores
    logs.append(f"GTIN válido: {total_validos}")
    logs.append(f"GTIN inválido zerado: {total_invalidos}")

    return df, logs


# =========================================================
# VALIDAÇÃO ISOLADA PARA USO RÁPIDO
# =========================================================
def gtin_valido(valor: Any) -> bool:
    """
    Retorna True se o valor for um GTIN válido.
    """
    gtin = limpar_gtin(valor)
    return validar_gtin_checksum(gtin)


# =========================================================
# NORMALIZAÇÃO OPCIONAL PARA TAMANHOS ACEITOS
# =========================================================
def normalizar_gtin_para_texto(valor: Any) -> str:
    """
    Retorna o GTIN limpo se for válido.
    Caso contrário, retorna string vazia.
    """
    gtin, valido = tratar_gtin(valor)
    if valido:
        return gtin
    return ""
