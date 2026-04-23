from __future__ import annotations

from typing import Any, List, Tuple
import random

import pandas as pd


# =========================================================
# HELPERS INTERNOS
# =========================================================
def _safe_text(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"nan", "none", "null"}:
            return ""
        return texto
    except Exception:
        return ""


def _somente_digitos(valor: Any) -> str:
    try:
        return "".join(ch for ch in _safe_text(valor) if ch.isdigit())
    except Exception:
        return ""


def _todos_digitos_iguais(gtin: str) -> bool:
    try:
        return bool(gtin) and len(set(gtin)) == 1
    except Exception:
        return False


def _sequencia_ciclica(base: str, tamanho: int) -> str:
    if not base or tamanho <= 0:
        return ""
    repeticoes = (tamanho // len(base)) + 2
    return (base * repeticoes)[:tamanho]


def _eh_sequencia_muito_padrao(gtin: str) -> bool:
    try:
        if not gtin:
            return False

        candidatos = [
            _sequencia_ciclica("0123456789", len(gtin)),
            _sequencia_ciclica("1234567890", len(gtin)),
            _sequencia_ciclica("9876543210", len(gtin)),
            _sequencia_ciclica("0987654321", len(gtin)),
        ]
        return gtin in candidatos
    except Exception:
        return False


def _repeticao_excessiva(gtin: str) -> bool:
    try:
        if not gtin:
            return False
        maior_repeticao = max(gtin.count(d) for d in set(gtin))
        return maior_repeticao >= max(len(gtin) - 1, 7)
    except Exception:
        return False


def _padrao_ciclico_curto(gtin: str) -> bool:
    """
    Detecta padrões artificiais como:
    12121212 / 123123123123 / 909090909090
    """
    try:
        if not gtin or len(gtin) < 8:
            return False

        for tamanho_bloco in (1, 2, 3, 4):
            if len(gtin) % tamanho_bloco != 0:
                continue
            bloco = gtin[:tamanho_bloco]
            if bloco and (bloco * (len(gtin) // tamanho_bloco)) == gtin:
                return True

        return False
    except Exception:
        return False


def _corpo_quase_zerado(gtin: str) -> bool:
    """
    Detecta códigos extremamente improváveis como:
    0000000000008 / 00000001 / 0000000000017
    """
    try:
        if not gtin or len(gtin) < 8:
            return False
        corpo = gtin[:-1]
        return corpo.count("0") >= max(len(corpo) - 1, 6)
    except Exception:
        return False


# =========================================================
# LIMPEZA DE GTIN
# =========================================================
def limpar_gtin(valor: Any) -> str:
    """Mantém apenas os dígitos do GTIN/EAN."""
    return _somente_digitos(valor)


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
    """Valida GTIN/EAN nos formatos 8, 12, 13 e 14 pelo checksum."""
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
# HEURÍSTICAS DE INTELIGÊNCIA / SUSPEITA
# =========================================================
def classificar_gtin(valor: Any) -> Tuple[str, str]:
    """
    Classifica o GTIN em:
    - vazio
    - invalido
    - suspeito
    - valido

    Retorna (status, motivo).
    """
    try:
        gtin = limpar_gtin(valor)

        if not gtin:
            return "vazio", "sem valor"

        if len(gtin) not in {8, 12, 13, 14}:
            return "invalido", "tamanho invalido"

        if not validar_gtin_checksum(gtin):
            return "invalido", "checksum invalido"

        if _todos_digitos_iguais(gtin):
            return "suspeito", "todos os digitos iguais"

        if _eh_sequencia_muito_padrao(gtin):
            return "suspeito", "sequencia muito padrao"

        if _repeticao_excessiva(gtin):
            return "suspeito", "repeticao excessiva de digitos"

        if _padrao_ciclico_curto(gtin):
            return "suspeito", "padrao ciclico curto"

        if _corpo_quase_zerado(gtin):
            return "suspeito", "corpo praticamente zerado"

        return "valido", "checksum ok"
    except Exception:
        return "invalido", "erro na classificacao"


def gtin_suspeito(valor: Any) -> bool:
    """Retorna True quando o GTIN passa no checksum, mas parece artificial/suspeito."""
    try:
        status, _ = classificar_gtin(valor)
        return status == "suspeito"
    except Exception:
        return False


def validar_gtin_inteligente(valor: Any) -> bool:
    """
    Validação mais rígida:
    - checksum ok
    - não pode ser padrão artificial/suspeito
    """
    try:
        status, _ = classificar_gtin(valor)
        return status == "valido"
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
    - string vazia se inválido/suspeito
    - bool indicando validade
    """
    try:
        gtin = limpar_gtin(valor)
        if not gtin:
            return "", False

        if validar_gtin_inteligente(gtin):
            return gtin, True

        return "", False
    except Exception:
        return "", False


def gtin_valido(valor: Any) -> bool:
    """Retorna True se o valor for um GTIN válido pela validação inteligente."""
    try:
        gtin = limpar_gtin(valor)
        return validar_gtin_inteligente(gtin)
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
            colunas_gtin.append(str(col))

    return colunas_gtin


# =========================================================
# CONTAGEM
# =========================================================
def contar_gtins_invalidos_df(df: pd.DataFrame) -> int:
    """
    Conta quantos GTINs inválidos ou suspeitos existem nas colunas GTIN/EAN.
    Vazios não contam como inválidos.
    """
    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return 0

        total_invalidos = 0
        colunas_gtin = encontrar_colunas_gtin(df)

        for coluna in colunas_gtin:
            for valor in df[coluna].tolist():
                gtin = limpar_gtin(valor)
                if not gtin:
                    continue
                if not validar_gtin_inteligente(gtin):
                    total_invalidos += 1

        return total_invalidos
    except Exception:
        return 0


def contar_gtins_suspeitos_df(df: pd.DataFrame) -> int:
    """Conta quantos GTINs suspeitos existem nas colunas GTIN/EAN."""
    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return 0

        total_suspeitos = 0
        colunas_gtin = encontrar_colunas_gtin(df)

        for coluna in colunas_gtin:
            for valor in df[coluna].tolist():
                if gtin_suspeito(valor):
                    total_suspeitos += 1

        return total_suspeitos
    except Exception:
        return 0


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
    GTIN inválido ou suspeito é zerado (fica vazio) automaticamente.
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
        total_suspeitos = 0

        for idx, valor in enumerate(df_saida[coluna].tolist(), start=1):
            texto_original = _safe_text(valor)
            gtin_original_limpo = limpar_gtin(texto_original)
            valores_originais.append(gtin_original_limpo)

            if not gtin_original_limpo:
                novos_valores.append("")
                total_vazios += 1
                continue

            status, motivo = classificar_gtin(gtin_original_limpo)

            if status == "valido":
                novos_valores.append(gtin_original_limpo)
                total_validos += 1
            else:
                novos_valores.append("")
                if status == "suspeito":
                    total_suspeitos += 1
                    logs.append(
                        f"Linha {idx}: GTIN suspeito zerado ({texto_original}) - motivo: {motivo}"
                    )
                else:
                    total_invalidos += 1
                    logs.append(
                        f"Linha {idx}: GTIN inválido zerado ({texto_original}) - motivo: {motivo}"
                    )

        df_saida[coluna] = novos_valores

        if preservar_coluna_original:
            nome_coluna_original = f"{coluna} Original"
            df_saida[nome_coluna_original] = valores_originais
            logs.append(f"Coluna original preservada: {nome_coluna_original}")

        logs.append(f"Coluna validada: {coluna}")
        logs.append(f"GTIN válido: {total_validos}")
        logs.append(f"GTIN inválido zerado: {total_invalidos}")
        logs.append(f"GTIN suspeito zerado: {total_suspeitos}")
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
    Procura automaticamente colunas GTIN/EAN e limpa inválidos/suspeitos,
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


def limpar_gtins_invalidos_df(
    df: pd.DataFrame,
    preservar_coluna_original: bool = False,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Função direta para a UI:
    procura colunas GTIN/EAN automaticamente e limpa inválidos/suspeitos.
    """
    return aplicar_validacao_gtin_em_colunas_automaticas(
        df=df,
        preservar_coluna_original=preservar_coluna_original,
    )


def limpar_gtins_invalidos_e_contar(
    df: pd.DataFrame,
    preservar_coluna_original: bool = False,
) -> Tuple[pd.DataFrame, int, List[str]]:
    """
    Retorna:
    - dataframe limpo
    - total de GTINs inválidos/suspeitos que foram zerados
    - logs completos
    """
    df_saida, logs = aplicar_validacao_gtin_em_colunas_automaticas(
        df=df,
        preservar_coluna_original=preservar_coluna_original,
    )
    resumo = resumir_logs_limpeza_gtin(logs)
    total_invalidos = int(resumo.get("invalidos", 0) or 0) + int(resumo.get("suspeitos", 0) or 0)
    return df_saida, total_invalidos, logs


def resumir_logs_limpeza_gtin(logs: List[str]) -> dict:
    """Resume os logs de limpeza/validação para uso na UI."""
    resumo = {
        "colunas_gtin": 0,
        "invalidos": 0,
        "suspeitos": 0,
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
        elif texto.startswith("GTIN suspeito zerado:"):
            try:
                resumo["suspeitos"] += int(texto.split(":")[-1].strip())
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
                if validar_gtin_inteligente(valor_limpo):
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


def gerar_gtins_apos_limpeza_invalidos(
    df: pd.DataFrame,
    prefixo: str = "789",
    preservar_coluna_original: bool = False,
) -> Tuple[pd.DataFrame, dict, List[str]]:
    """
    Fluxo completo:
    1. limpa GTINs inválidos/suspeitos
    2. gera GTINs válidos somente nos vazios
    3. devolve resumo e logs para a UI
    """
    logs_finais: List[str] = []

    try:
        df_limpo, logs_limpeza = aplicar_validacao_gtin_em_colunas_automaticas(
            df=df,
            preservar_coluna_original=preservar_coluna_original,
        )
        logs_finais.extend(logs_limpeza)

        resumo_limpeza = resumir_logs_limpeza_gtin(logs_limpeza)

        df_gerado, logs_geracao = gerar_gtins_validos_em_colunas_automaticas(
            df=df_limpo,
            prefixo=prefixo,
            apenas_vazios=True,
        )
        logs_finais.extend(logs_geracao)

        total_gerados = 0
        for item in logs_geracao:
            texto = str(item)
            if texto.startswith("GTIN gerados:"):
                try:
                    total_gerados += int(texto.split(":")[-1].strip())
                except Exception:
                    pass

        resumo = {
            "colunas_gtin": int(resumo_limpeza.get("colunas_gtin", 0) or 0),
            "invalidos_limpos": int(resumo_limpeza.get("invalidos", 0) or 0),
            "suspeitos_limpos": int(resumo_limpeza.get("suspeitos", 0) or 0),
            "validos_mantidos": int(resumo_limpeza.get("validos", 0) or 0),
            "vazios_originais": int(resumo_limpeza.get("vazios", 0) or 0),
            "gtins_gerados": int(total_gerados),
        }

        return df_gerado, resumo, logs_finais

    except Exception as e:
        logs_finais.append(f"Erro no fluxo limpar+gerar GTIN: {e}")
        return (
            df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(),
            {
                "colunas_gtin": 0,
                "invalidos_limpos": 0,
                "suspeitos_limpos": 0,
                "validos_mantidos": 0,
                "vazios_originais": 0,
                "gtins_gerados": 0,
            },
            logs_finais,
        )
