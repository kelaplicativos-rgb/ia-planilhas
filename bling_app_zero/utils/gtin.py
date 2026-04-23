from __future__ import annotations

from typing import Any, List, Tuple
import random

import pandas as pd

from bling_app_zero.utils.limpeza import limpar_texto, somente_digitos


# =========================================================
# LIMPEZA DE GTIN
# =========================================================
def limpar_gtin(valor: Any) -> str:
    """Mantém apenas os dígitos do GTIN/EAN."""
    try:
        return somente_digitos(valor)
    except Exception:
        try:
            return "".join(ch for ch in str(valor or "") if ch.isdigit())
        except Exception:
            return ""


# =========================================================
# CHECKSUM / VALIDAÇÃO
# =========================================================
def calcular_digito_verificador_gtin(corpo: str) -> str:
    """
    Calcula o dígito verificador para GTIN-8/12/13/14 a partir do corpo
    (sem o último dígito).
    """
    corpo = limpar_gtin(corpo)
    if not corpo or not corpo.isdigit():
        raise ValueError("Corpo do GTIN inválido para cálculo do dígito.")

    if len(corpo) not in {7, 11, 12, 13}:
        raise ValueError("Tamanho do corpo do GTIN inválido.")

    soma = 0
    peso = 3
    for numero in reversed(corpo):
        soma += int(numero) * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return str(calculado)


def validar_gtin_checksum(gtin: str) -> bool:
    """Valida GTIN/EAN nos formatos 8, 12, 13 e 14."""
    try:
        gtin = limpar_gtin(gtin)
        if not gtin or not gtin.isdigit():
            return False

        if len(gtin) not in {8, 12, 13, 14}:
            return False

        corpo = gtin[:-1]
        dv = gtin[-1]
        return calcular_digito_verificador_gtin(corpo) == dv
    except Exception:
        return False


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
    try:
        gtin = limpar_gtin(valor)
        if not gtin:
            return "", False

        if validar_gtin_checksum(gtin):
            return gtin, True

        return "", False
    except Exception:
        return "", False


def gtin_valido(valor: Any) -> bool:
    """Retorna True se o valor for um GTIN válido."""
    try:
        gtin = limpar_gtin(valor)
        return validar_gtin_checksum(gtin)
    except Exception:
        return False


def normalizar_gtin_para_texto(valor: Any) -> str:
    """Retorna o GTIN limpo se for válido. Caso contrário, retorna string vazia."""
    try:
        gtin, valido = tratar_gtin(valor)
        if valido:
            return gtin
        return ""
    except Exception:
        return ""


# =========================================================
# LOCALIZAÇÃO DE COLUNAS GTIN/EAN
# =========================================================
def encontrar_colunas_gtin(df: pd.DataFrame) -> List[str]:
    """Procura automaticamente colunas com nome contendo GTIN ou EAN."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []

    colunas_gtin: List[str] = []
    for col in df.columns:
        nome = str(col).strip().lower()
        if "gtin" in nome or "ean" in nome:
            colunas_gtin.append(col)

    return colunas_gtin


# =========================================================
# LIMPEZA EM DATAFRAME
# =========================================================
def aplicar_validacao_gtin_df(
    df: pd.DataFrame,
    coluna: str,
    preservar_coluna_original: bool = False,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Valida a coluna de GTIN em um DataFrame.
    GTIN inválido é zerado (fica vazio) automaticamente.
    """
    logs: List[str] = []

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

        df_saida = df.copy()
        novos_valores: List[str] = []
        valores_originais: List[str] = []
        total_invalidos = 0
        total_validos = 0
        total_vazios = 0

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

            gtin_corrigido, valido = tratar_gtin(gtin_original_limpo)
            if valido:
                novos_valores.append(gtin_corrigido)
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

        logs.append(f"Coluna validada: {coluna}")
        logs.append(f"GTIN válido: {total_validos}")
        logs.append(f"GTIN inválido zerado: {total_invalidos}")
        logs.append(f"GTIN vazio: {total_vazios}")

        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro ao validar GTIN na coluna '{coluna}': {e}")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(), logs


def aplicar_validacao_gtin_em_colunas_automaticas(
    df: pd.DataFrame,
    preservar_coluna_original: bool = False,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Procura automaticamente colunas GTIN/EAN e limpa apenas os inválidos,
    deixando vazios.
    """
    logs: List[str] = []

    try:
        if df is None or not isinstance(df, pd.DataFrame):
            logs.append("DataFrame inválido para varredura automática de GTIN.")
            return pd.DataFrame(), logs

        if df.empty:
            logs.append("DataFrame vazio para varredura automática de GTIN.")
            return df.copy(), logs

        df_saida = df.copy()
        colunas_gtin = encontrar_colunas_gtin(df_saida)

        if not colunas_gtin:
            logs.append("Nenhuma coluna GTIN/EAN encontrada para validação.")
            return df_saida, logs

        for coluna in colunas_gtin:
            df_saida, logs_coluna = aplicar_validacao_gtin_df(
                df_saida,
                coluna,
                preservar_coluna_original=preservar_coluna_original,
            )
            logs.extend(logs_coluna)

        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro na varredura automática de GTIN: {e}")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(), logs


def resumir_logs_limpeza_gtin(logs: List[str]) -> dict:
    """Resume os logs de limpeza/validação para uso na UI."""
    resumo = {
        "colunas_gtin": 0,
        "invalidos": 0,
        "validos": 0,
        "vazios": 0,
    }

    for item in logs or []:
        texto = str(item)

        if texto.startswith("Coluna validada:"):
            resumo["colunas_gtin"] += 1
        elif texto.startswith("GTIN inválido zerado:"):
            try:
                resumo["invalidos"] += int(texto.split(":")[-1].strip())
            except Exception:
                pass
        elif texto.startswith("GTIN válido:"):
            try:
                resumo["validos"] += int(texto.split(":")[-1].strip())
            except Exception:
                pass
        elif texto.startswith("GTIN vazio:"):
            try:
                resumo["vazios"] += int(texto.split(":")[-1].strip())
            except Exception:
                pass

    return resumo


# =========================================================
# GERAÇÃO GTIN-13
# =========================================================
def gerar_gtin_13(prefixo: str = "789", sequencia: str | None = None) -> str:
    """
    Gera um GTIN-13 válido.
    prefixo padrão BR: 789.
    """
    prefixo_limpo = limpar_gtin(prefixo) or "789"

    if len(prefixo_limpo) >= 12:
        corpo = prefixo_limpo[:12]
    else:
        faltantes = 12 - len(prefixo_limpo)

        if sequencia is None:
            numero = random.randint(0, (10**faltantes) - 1)
            sequencia = str(numero).zfill(faltantes)
        else:
            sequencia = limpar_gtin(sequencia).zfill(faltantes)[:faltantes]

        corpo = f"{prefixo_limpo}{sequencia}"[:12]

    dv = calcular_digito_verificador_gtin(corpo)
    return f"{corpo}{dv}"


def gerar_gtins_validos_df(
    df: pd.DataFrame,
    coluna: str,
    prefixo: str = "789",
    apenas_vazios: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Preenche GTINs válidos em uma coluna.
    Por padrão gera apenas nos vazios.
    """
    logs: List[str] = []

    try:
        if df is None or not isinstance(df, pd.DataFrame):
            logs.append("DataFrame inválido para geração de GTIN.")
            return pd.DataFrame(), logs

        if df.empty:
            logs.append("DataFrame vazio para geração de GTIN.")
            return df.copy(), logs

        if not coluna or coluna not in df.columns:
            logs.append(f"Coluna de GTIN não encontrada: {coluna}")
            return df.copy(), logs

        df_saida = df.copy()
        total_gerados = 0

        for idx, valor in enumerate(df_saida[coluna].tolist(), start=1):
            valor_limpo = limpar_gtin(valor)

            if apenas_vazios:
                if valor_limpo:
                    continue
            else:
                if valor_limpo and validar_gtin_checksum(valor_limpo):
                    continue

            gtin_gerado = gerar_gtin_13(prefixo=prefixo, sequencia=str(idx))
            df_saida.at[df_saida.index[idx - 1], coluna] = gtin_gerado
            total_gerados += 1
            logs.append(f"Linha {idx}: GTIN gerado ({gtin_gerado})")

        logs.append(f"Coluna gerada: {coluna}")
        logs.append(f"GTIN gerados: {total_gerados}")
        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro ao gerar GTIN na coluna '{coluna}': {e}")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(), logs


def gerar_gtins_validos_em_colunas_automaticas(
    df: pd.DataFrame,
    prefixo: str = "789",
    apenas_vazios: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Procura automaticamente colunas GTIN/EAN e gera GTINs válidos.
    """
    logs: List[str] = []

    try:
        if df is None or not isinstance(df, pd.DataFrame):
            logs.append("DataFrame inválido para geração automática de GTIN.")
            return pd.DataFrame(), logs

        if df.empty:
            logs.append("DataFrame vazio para geração automática de GTIN.")
            return df.copy(), logs

        df_saida = df.copy()
        colunas_gtin = encontrar_colunas_gtin(df_saida)

        if not colunas_gtin:
            logs.append("Nenhuma coluna GTIN/EAN encontrada para geração.")
            return df_saida, logs

        for coluna in colunas_gtin:
            df_saida, logs_coluna = gerar_gtins_validos_df(
                df_saida,
                coluna=coluna,
                prefixo=prefixo,
                apenas_vazios=apenas_vazios,
            )
            logs.extend(logs_coluna)

        return df_saida, logs

    except Exception as e:
        logs.append(f"Erro na geração automática de GTIN: {e}")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(), logs



def contar_gtins_invalidos_df(df: pd.DataFrame) -> int:
    """Conta GTINs inválidos em todas as colunas GTIN/EAN detectadas automaticamente."""
    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return 0

        total_invalidos = 0
        for coluna in encontrar_colunas_gtin(df):
            serie = df[coluna].fillna("").astype(str)
            for valor in serie.tolist():
                gtin = limpar_gtin(valor)
                if not gtin:
                    continue
                if not validar_gtin_checksum(gtin):
                    total_invalidos += 1
        return total_invalidos
    except Exception:
        return 0

