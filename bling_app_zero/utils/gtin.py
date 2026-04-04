import re
from typing import List, Tuple


# =========================
# LIMPEZA BÁSICA
# =========================
def limpar_gtin(valor) -> str:
    """
    Remove tudo que não for número.
    Retorna string vazia para None, NaN textual e valores vazios.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()

    if not texto or texto.lower() in {"nan", "none", "null"}:
        return ""

    return re.sub(r"\D", "", texto)


# =========================
# VALIDADOR DE GTIN
# =========================
def validar_gtin(gtin: str) -> bool:
    """
    Valida GTIN-8, GTIN-12, GTIN-13 e GTIN-14.
    """
    if not gtin or not isinstance(gtin, str):
        return False

    if not gtin.isdigit():
        return False

    if len(gtin) not in (8, 12, 13, 14):
        return False

    soma = 0
    multiplicador = 3

    # calcula usando o corpo, da direita para a esquerda
    for digito in reversed(gtin[:-1]):
        soma += int(digito) * multiplicador
        multiplicador = 1 if multiplicador == 3 else 3

    resto = soma % 10
    digito_verificador = 0 if resto == 0 else 10 - resto

    return digito_verificador == int(gtin[-1])


# =========================
# PROCESSAMENTO UNITÁRIO
# =========================
def tratar_gtin(valor) -> Tuple[str, bool]:
    """
    Limpa e valida um único GTIN.
    Se inválido, retorna string vazia.
    """
    gtin_limpo = limpar_gtin(valor)

    if not gtin_limpo:
        return "", False

    if validar_gtin(gtin_limpo):
        return gtin_limpo, True

    return "", False


# =========================
# UTILITÁRIOS INTERNOS
# =========================
def _valor_original_preenchido(valor) -> bool:
    if valor is None:
        return False

    texto = str(valor).strip()
    return bool(texto) and texto.lower() not in {"nan", "none", "null"}


def _nome_coluna_linha(coluna: str) -> str:
    return coluna if coluna else "GTIN"


# =========================
# APLICAR EM UMA COLUNA
# =========================
def aplicar_validacao_gtin(df, coluna: str = "gtin"):
    """
    Aplica limpeza e validação em uma coluna do DataFrame.
    GTIN inválido vira string vazia.
    """
    logs: List[str] = []
    total_invalidos = 0

    if coluna not in df.columns:
        return df, [f"⚠️ Coluna '{coluna}' não encontrada"]

    novos_valores = []

    for i, valor in enumerate(df[coluna]):
        gtin_corrigido, valido = tratar_gtin(valor)

        if not valido and _valor_original_preenchido(valor):
            total_invalidos += 1
            logs.append(
                f"Linha {i + 1}: {_nome_coluna_linha(coluna)} inválido removido ({valor})"
            )

        novos_valores.append(gtin_corrigido)

    df[coluna] = novos_valores
    logs.append(
        f"Total inválidos corrigidos na coluna '{coluna}': {total_invalidos}"
    )

    return df, logs


# =========================
# APLICAR NOS DOIS CAMPOS DO BLING
# =========================
def aplicar_validacao_gtins_bling(
    df,
    coluna_gtin: str = "GTIN/EAN",
    coluna_gtin_tributario: str = "GTIN/EAN tributário",
    copiar_gtin_para_tributario_quando_vazio: bool = True,
):
    """
    Valida os dois campos de GTIN do Bling.

    Regras:
    - GTIN inválido -> ""
    - GTIN tributário inválido -> ""
    - Se o tributário estiver vazio e o GTIN normal for válido,
      pode copiar o GTIN normal para o tributário
    """
    logs: List[str] = []

    if coluna_gtin not in df.columns:
        df[coluna_gtin] = ""
        logs.append(f"⚠️ Coluna '{coluna_gtin}' não encontrada. Criada vazia.")

    if coluna_gtin_tributario not in df.columns:
        df[coluna_gtin_tributario] = ""
        logs.append(
            f"⚠️ Coluna '{coluna_gtin_tributario}' não encontrada. Criada vazia."
        )

    novos_gtins = []
    novos_gtins_tributarios = []
    total_invalidos_gtin = 0
    total_invalidos_gtin_tributario = 0
    total_copiados_para_tributario = 0

    for i in range(len(df)):
        valor_gtin = df.at[df.index[i], coluna_gtin]
        valor_gtin_trib = df.at[df.index[i], coluna_gtin_tributario]

        gtin_corrigido, gtin_valido = tratar_gtin(valor_gtin)
        gtin_trib_corrigido, gtin_trib_valido = tratar_gtin(valor_gtin_trib)

        if not gtin_valido and _valor_original_preenchido(valor_gtin):
            total_invalidos_gtin += 1
            logs.append(
                f"Linha {i + 1}: {coluna_gtin} inválido removido ({valor_gtin})"
            )

        if not gtin_trib_valido and _valor_original_preenchido(valor_gtin_trib):
            total_invalidos_gtin_tributario += 1
            logs.append(
                f"Linha {i + 1}: {coluna_gtin_tributario} inválido removido ({valor_gtin_trib})"
            )

        if (
            copiar_gtin_para_tributario_quando_vazio
            and gtin_corrigido
            and not gtin_trib_corrigido
        ):
            gtin_trib_corrigido = gtin_corrigido
            total_copiados_para_tributario += 1
            logs.append(
                f"Linha {i + 1}: {coluna_gtin_tributario} preenchido com o valor de {coluna_gtin}"
            )

        novos_gtins.append(gtin_corrigido)
        novos_gtins_tributarios.append(gtin_trib_corrigido)

    df[coluna_gtin] = novos_gtins
    df[coluna_gtin_tributario] = novos_gtins_tributarios

    logs.append(
        f"Total inválidos corrigidos em '{coluna_gtin}': {total_invalidos_gtin}"
    )
    logs.append(
        f"Total inválidos corrigidos em '{coluna_gtin_tributario}': {total_invalidos_gtin_tributario}"
    )
    logs.append(
        f"Total de cópias de '{coluna_gtin}' para '{coluna_gtin_tributario}': {total_copiados_para_tributario}"
    )

    return df, logs
