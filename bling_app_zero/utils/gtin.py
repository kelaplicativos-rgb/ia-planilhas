from __future__ import annotations

from typing import Any
import random

import pandas as pd

from bling_app_zero.utils.limpeza import limpar_texto, somente_digitos


# =========================================================
# GERAÇÃO DE GTIN VÁLIDO
# =========================================================
def _calcular_digito_gtin(corpo: str) -> str:
    try:
        if not corpo or not corpo.isdigit():
            return "0"

        soma = 0
        peso = 3

        for numero in reversed([int(d) for d in corpo]):
            soma += numero * peso
            peso = 1 if peso == 3 else 3

        return str((10 - (soma % 10)) % 10)
    except Exception:
        return "0"


def gerar_gtin_valido(tamanho: int = 13) -> str:
    """
    Gera um GTIN matematicamente válido.
    Padrão: EAN-13.
    """
    try:
        if tamanho not in {8, 12, 13, 14}:
            tamanho = 13

        corpo = "".join(str(random.randint(0, 9)) for _ in range(tamanho - 1))
        return corpo + _calcular_digito_gtin(corpo)
    except Exception:
        return ""


# =========================================================
# LIMPEZA DE GTIN
# =========================================================
def limpar_gtin(valor: Any) -> str:
    """
    Mantém apenas os dígitos do GTIN/EAN.
    """
    try:
        return somente_digitos(valor)
    except Exception:
        return ""


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
    try:
        if not gtin or not isinstance(gtin, str) or not gtin.isdigit():
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
    except Exception:
        return False


# =========================================================
# TRATAMENTO FINAL DE GTIN
# =========================================================
def tratar_gtin(
    valor: Any,
    modo: str = "limpar",
    tamanho_gerado: int = 13,
) -> tuple[str, bool]:
    """
    Limpa e valida o GTIN.

    modo:
    - "limpar" => GTIN inválido vira vazio
    - "gerar"  => GTIN inválido vira GTIN válido automático

    Retorna:
    - GTIN final
    - bool indicando validade final
    """
    try:
        gtin = limpar_gtin(valor)

        if not gtin:
            return "", False

        if validar_gtin_checksum(gtin):
            return gtin, True

        if str(modo).strip().lower() == "gerar":
            novo_gtin = gerar_gtin_valido(tamanho=tamanho_gerado)
            return novo_gtin, bool(novo_gtin)

        return "", False
    except Exception:
        return "", False


# =========================================================
# APLICA VALIDAÇÃO EM DATAFRAME
# =========================================================
def aplicar_validacao_gtin_df(
    df: pd.DataFrame,
    coluna: str,
    preservar_coluna_original: bool = False,
    modo: str = "limpar",
    tamanho_gerado: int = 13,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Valida a coluna de GTIN em um DataFrame.

    modo:
    - "limpar": GTIN inválido fica vazio
    - "gerar": GTIN inválido vira GTIN válido automático

    Parâmetros:
    - df: DataFrame de entrada
    - coluna: nome da coluna de GTIN/EAN
    - preservar_coluna_original: se True, cria "<coluna> Original"
      com o valor original limpo antes da validação
    - modo: estratégia para inválidos
    - tamanho_gerado: tamanho do GTIN gerado automaticamente

    Retorna:
    - DataFrame atualizado
    - lista de logs
    """
    logs: list[str] = []

    try:
        if df is None or not isinstance(df, pd.DataFrame):
            logs.append("DataFrame inválido para validação de GTIN.")
            return pd.DataFrame(), logs

        if df.empty:
            logs.append("DataFrame vazio para validação de GTIN.")
            return df.copy(), logs

        if not coluna or coluna not in df.columns:
            logs.append(f"Coluna de GTIN não encontrada: {coluna}")
            return df.copy(), logs

        modo = str(modo or "limpar").strip().lower()
        if modo not in {"limpar", "gerar"}:
            modo = "limpar"

        df_saida = df.copy()

        novos_valores: list[str] = []
        valores_originais: list[str] = []

        total_invalidos = 0
        total_validos = 0
        total_vazios = 0
        total_gerados = 0

        for idx, valor in enumerate(df_saida[coluna].tolist(), start=1):
            try:
                texto_original = limpar_texto(valor)
            except Exception:
                texto_original = str(valor).strip() if valor is not None else ""

            gtin_original_limpo = limpar_gtin(texto_original)
            valores_originais.append(gtin_original_limpo)

            if not gtin_original_limpo:
                novos_valores.append("")
                total_vazios += 1
                continue

            gtin_corrigido, valido = tratar_gtin(
                gtin_original_limpo,
                modo=modo,
                tamanho_gerado=tamanho_gerado,
            )

            if valido:
                novos_valores.append(gtin_corrigido)

                if gtin_corrigido != gtin_original_limpo:
                    total_invalidos += 1
                    total_gerados += 1
                    logs.append(
                        f"Linha {idx}: GTIN inválido substituído por GTIN válido automático"
                    )
                else:
                    total_validos += 1
            else:
                novos_valores.append("")
                total_invalidos += 1
                logs.append(f"Linha {idx}: GTIN inválido zerado ({texto_original})")

        df_saida[coluna] = novos_valores

        if preservar_coluna_original:
            nome_coluna_original = f"{coluna} Original"
            df_saida[nome_coluna_original] = valores_originais
            logs.append(f"Coluna original preservada: {nome_coluna_original}")

        logs.append(f"GTIN válido mantido: {total_validos}")
        logs.append(f"GTIN inválido tratado: {total_invalidos}")
        logs.append(f"GTIN gerado automaticamente: {total_gerados}")
        logs.append(f"GTIN vazio: {total_vazios}")

        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro ao validar GTIN na coluna '{coluna}': {e}")
        if isinstance(df, pd.DataFrame):
            return df.copy(), logs
        return pd.DataFrame(), logs


# =========================================================
# VALIDAÇÃO ISOLADA PARA USO RÁPIDO
# =========================================================
def gtin_valido(valor: Any) -> bool:
    """
    Retorna True se o valor for um GTIN válido.
    """
    try:
        gtin = limpar_gtin(valor)
        return validar_gtin_checksum(gtin)
    except Exception:
        return False


# =========================================================
# NORMALIZAÇÃO OPCIONAL PARA TAMANHOS ACEITOS
# =========================================================
def normalizar_gtin_para_texto(
    valor: Any,
    modo: str = "limpar",
    tamanho_gerado: int = 13,
) -> str:
    """
    Retorna o GTIN final tratado.
    Caso inválido:
    - limpa, ou
    - gera automático, conforme modo
    """
    try:
        gtin, valido = tratar_gtin(
            valor,
            modo=modo,
            tamanho_gerado=tamanho_gerado,
        )
        if valido:
            return gtin
        return ""
    except Exception:
        return ""


# =========================================================
# LIMPEZA AUTOMÁTICA EM MÚLTIPLAS COLUNAS GTIN/EAN
# =========================================================
def aplicar_validacao_gtin_em_colunas_automaticas(
    df: pd.DataFrame,
    preservar_coluna_original: bool = False,
    modo: str = "limpar",
    tamanho_gerado: int = 13,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Procura automaticamente colunas com nome contendo GTIN ou EAN
    e aplica a validação em todas elas.
    """
    logs: list[str] = []

    try:
        if df is None or not isinstance(df, pd.DataFrame):
            logs.append("DataFrame inválido para varredura automática de GTIN.")
            return pd.DataFrame(), logs

        if df.empty:
            logs.append("DataFrame vazio para varredura automática de GTIN.")
            return df.copy(), logs

        df_saida = df.copy()

        colunas_gtin = [
            col
            for col in df_saida.columns
            if "gtin" in str(col).strip().lower()
            or "ean" in str(col).strip().lower()
        ]

        if not colunas_gtin:
            logs.append("Nenhuma coluna GTIN/EAN encontrada para validação.")
            return df_saida, logs

        for coluna in colunas_gtin:
            df_saida, logs_coluna = aplicar_validacao_gtin_df(
                df_saida,
                coluna,
                preservar_coluna_original=preservar_coluna_original,
                modo=modo,
                tamanho_gerado=tamanho_gerado,
            )
            logs.append(f"Coluna validada: {coluna}")
            logs.extend(logs_coluna)

        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro na varredura automática de GTIN: {e}")
        if isinstance(df, pd.DataFrame):
            return df.copy(), logs
        return pd.DataFrame(), logs
