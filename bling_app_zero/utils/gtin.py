import re
import pandas as pd


# =========================
# LIMPEZA
# =========================
def limpar_gtin(valor):
    if pd.isna(valor):
        return ""

    valor = re.sub(r"\D", "", str(valor).strip())

    if not valor:
        return ""

    return valor


# =========================
# VALIDAÇÃO
# =========================
def validar_gtin(gtin):
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in (8, 12, 13, 14):
        return False

    soma = 0
    peso = 3

    for digito in reversed(gtin[:-1]):
        soma += int(digito) * peso
        peso = 1 if peso == 3 else 3

    resto = soma % 10
    dv = 0 if resto == 0 else 10 - resto

    return dv == int(gtin[-1])


# =========================
# TRATAMENTO INDIVIDUAL
# =========================
def tratar_gtin(valor):
    gtin = limpar_gtin(valor)

    if not gtin:
        return ""

    if validar_gtin(gtin):
        return gtin

    return ""


# =========================
# TRATAMENTO FINAL BLING
# =========================
def tratar_gtins_bling(df):
    col_gtin = "GTIN/EAN"
    col_gtin_trib = "GTIN/EAN tributário"

    if col_gtin not in df.columns:
        df[col_gtin] = ""

    if col_gtin_trib not in df.columns:
        df[col_gtin_trib] = ""

    novos_gtin = []
    novos_gtin_trib = []

    for i in range(len(df)):
        gtin = tratar_gtin(df.at[df.index[i], col_gtin])
        gtin_trib = tratar_gtin(df.at[df.index[i], col_gtin_trib])

        # REGRA PRINCIPAL
        if gtin and not gtin_trib:
            gtin_trib = gtin

        novos_gtin.append(gtin)
        novos_gtin_trib.append(gtin_trib)

    df[col_gtin] = novos_gtin
    df[col_gtin_trib] = novos_gtin_trib

    return df
