import re

# =========================
# LIMPEZA BÁSICA
# =========================
def limpar_gtin(valor):
    if valor is None:
        return ""

    # Remove tudo que não for número
    valor = re.sub(r"\D", "", str(valor))

    return valor


# =========================
# VALIDADOR DE GTIN
# =========================
def validar_gtin(gtin):
    if not gtin:
        return False

    # Só aceita números
    if not gtin.isdigit():
        return False

    tamanho = len(gtin)

    # Aceita padrões oficiais
    if tamanho not in [8, 12, 13, 14]:
        return False

    # Algoritmo de validação (módulo 10)
    soma = 0
    reverso = gtin[::-1]

    for i, digito in enumerate(reverso):
        n = int(digito)

        if i % 2 == 1:
            soma += n * 3
        else:
            soma += n

    return soma % 10 == 0


# =========================
# PROCESSAMENTO COMPLETO
# =========================
def tratar_gtin(valor):
    gtin_limpo = limpar_gtin(valor)

    if validar_gtin(gtin_limpo):
        return gtin_limpo, True
    else:
        return "", False


# =========================
# APLICAR NO DATAFRAME
# =========================
def aplicar_validacao_gtin(df, coluna="gtin"):
    logs = []
    total_invalidos = 0

    if coluna not in df.columns:
        return df, ["⚠️ Coluna GTIN não encontrada"]

    novos_valores = []

    for i, valor in enumerate(df[coluna]):
        gtin_corrigido, valido = tratar_gtin(valor)

        if not valido and valor:
            total_invalidos += 1
            logs.append(f"Linha {i+1}: GTIN inválido removido ({valor})")

        novos_valores.append(gtin_corrigido)

    df[coluna] = novos_valores

    logs.append(f"Total inválidos corrigidos: {total_invalidos}")

    return df, logs
