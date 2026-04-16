
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd


GTIN_LENGTHS_VALIDOS = {8, 12, 13, 14}


@dataclass
class ValidationResult:
    aprovado: bool = False
    erros: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    corrigido_automaticamente: List[str] = field(default_factory=list)
    linhas_validas: int = 0
    linhas_invalidas: int = 0
    df_resultado: Optional[pd.DataFrame] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "aprovado": self.aprovado,
            "erros": self.erros,
            "avisos": self.avisos,
            "corrigido_automaticamente": self.corrigido_automaticamente,
            "linhas_validas": self.linhas_validas,
            "linhas_invalidas": self.linhas_invalidas,
        }


def _normalizar_coluna_nome(nome: object) -> str:
    return str(nome or "").strip()


def _normalizar_texto(valor: object) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _to_numeric_safe(valor: object) -> Optional[float]:
    texto = _normalizar_texto(valor)
    if not texto:
        return None

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


def _somente_digitos(valor: object) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin.isdigit():
        return False

    if len(gtin) not in GTIN_LENGTHS_VALIDOS:
        return False

    digits = [int(d) for d in gtin]
    check_digit = digits[-1]
    base_digits = digits[:-1]

    soma = 0
    peso_tres = True
    for digito in reversed(base_digits):
        soma += digito * (3 if peso_tres else 1)
        peso_tres = not peso_tres

    calculado = (10 - (soma % 10)) % 10
    return calculado == check_digit


def _limpar_gtin_invalido_serie(serie: pd.Series) -> Tuple[pd.Series, int]:
    corrigidos = 0

    def _corrigir(valor: object) -> str:
        nonlocal corrigidos
        digitos = _somente_digitos(valor)

        if not digitos:
            return ""

        if len(digitos) not in GTIN_LENGTHS_VALIDOS or not _gtin_checksum_valido(digitos):
            corrigidos += 1
            return ""

        return digitos

    return serie.apply(_corrigir), corrigidos


def _normalizar_imagens_pipe_serie(serie: pd.Series) -> Tuple[pd.Series, int]:
    corrigidos = 0

    def _corrigir(valor: object) -> str:
        nonlocal corrigidos
        texto = _normalizar_texto(valor)
        if not texto:
            return ""

        original = texto
        for separador in [";", ",", "\n"]:
            texto = texto.replace(separador, "|")

        partes = [parte.strip() for parte in texto.split("|") if parte.strip()]
        texto = "|".join(partes)

        if texto != original:
            corrigidos += 1

        return texto

    return serie.apply(_corrigir), corrigidos


def _validar_colunas_esperadas(df: pd.DataFrame, colunas_esperadas: List[str]) -> List[str]:
    erros: List[str] = []
    colunas_df = [_normalizar_coluna_nome(c) for c in df.columns]

    faltantes = [c for c in colunas_esperadas if c not in colunas_df]
    extras = [c for c in colunas_df if c not in colunas_esperadas]

    if faltantes:
        erros.append(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

    if not faltantes and colunas_df != colunas_esperadas:
        erros.append("A ordem das colunas não está idêntica ao modelo esperado.")

    if extras:
        erros.append(f"Colunas extras encontradas fora do modelo: {', '.join(extras)}")

    return erros


def _validar_campos_obrigatorios(
    df: pd.DataFrame,
    campos_obrigatorios: List[str],
) -> List[str]:
    erros: List[str] = []

    for campo in campos_obrigatorios:
        if campo not in df.columns:
            erros.append(f"Campo obrigatório ausente no DataFrame: {campo}")
            continue

        vazias = df[campo].apply(lambda v: _normalizar_texto(v) == "").sum()
        if vazias > 0:
            erros.append(f"Campo obrigatório '{campo}' vazio em {int(vazias)} linha(s).")

    return erros


def _validar_preco(df: pd.DataFrame, nome_coluna: str) -> List[str]:
    erros: List[str] = []
    if nome_coluna not in df.columns:
        return erros

    invalidas = 0
    for valor in df[nome_coluna]:
        numero = _to_numeric_safe(valor)
        if numero is None or numero < 0:
            invalidas += 1

    if invalidas > 0:
        erros.append(f"Campo '{nome_coluna}' inválido em {invalidas} linha(s).")

    return erros


def _validar_estoque(df: pd.DataFrame, nome_coluna: str) -> List[str]:
    erros: List[str] = []
    if nome_coluna not in df.columns:
        return erros

    invalidas = 0
    for valor in df[nome_coluna]:
        numero = _to_numeric_safe(valor)
        if numero is None:
            invalidas += 1
            continue
        if int(numero) != numero:
            invalidas += 1
            continue
        if numero < 0:
            invalidas += 1

    if invalidas > 0:
        erros.append(f"Campo '{nome_coluna}' inválido em {invalidas} linha(s).")

    return erros


def _campos_base_por_operacao(operacao: str) -> Tuple[List[str], List[str]]:
    operacao_normalizada = _normalizar_texto(operacao).lower()

    if operacao_normalizada == "estoque":
        colunas = [
            "Código",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
        obrigatorios = [
            "Código",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
        return colunas, obrigatorios

    colunas = [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
    ]
    obrigatorios = [
        "Código",
        "Descrição",
        "Preço de venda",
    ]
    return colunas, obrigatorios


def validar_dataframe_bling(
    df: pd.DataFrame,
    operacao: str,
    colunas_modelo: Optional[List[str]] = None,
    campos_obrigatorios_extras: Optional[List[str]] = None,
) -> ValidationResult:
    resultado = ValidationResult()

    if df is None or not isinstance(df, pd.DataFrame):
        resultado.erros.append("DataFrame final ausente ou inválido.")
        return resultado

    df_validado = df.copy()
    operacao_normalizada = _normalizar_texto(operacao).lower()

    colunas_base, obrigatorios_base = _campos_base_por_operacao(operacao_normalizada)
    colunas_esperadas = colunas_modelo or colunas_base
    campos_obrigatorios = list(obrigatorios_base)

    if campos_obrigatorios_extras:
        for campo in campos_obrigatorios_extras:
            if campo not in campos_obrigatorios:
                campos_obrigatorios.append(campo)

    if "GTIN/EAN" in df_validado.columns:
        df_validado["GTIN/EAN"], qtd_corrigidos = _limpar_gtin_invalido_serie(df_validado["GTIN/EAN"])
        if qtd_corrigidos > 0:
            resultado.corrigido_automaticamente.append(
                f"GTIN inválido limpo em {qtd_corrigidos} linha(s)."
            )

    for coluna_imagem in ["Imagem", "Imagens", "URL Imagens", "Link Imagens"]:
        if coluna_imagem in df_validado.columns:
            df_validado[coluna_imagem], qtd_corrigidos = _normalizar_imagens_pipe_serie(
                df_validado[coluna_imagem]
            )
            if qtd_corrigidos > 0:
                resultado.corrigido_automaticamente.append(
                    f"Separador de imagens normalizado com pipe na coluna '{coluna_imagem}' em {qtd_corrigidos} linha(s)."
                )

    resultado.erros.extend(_validar_colunas_esperadas(df_validado, colunas_esperadas))
    resultado.erros.extend(_validar_campos_obrigatorios(df_validado, campos_obrigatorios))

    if operacao_normalizada == "estoque":
        resultado.erros.extend(_validar_preco(df_validado, "Preço unitário (OBRIGATÓRIO)"))
        resultado.erros.extend(_validar_estoque(df_validado, "Balanço (OBRIGATÓRIO)"))
    else:
        resultado.erros.extend(_validar_preco(df_validado, "Preço de venda"))

    total_linhas = len(df_validado)

    if resultado.erros:
        resultado.aprovado = False
        resultado.linhas_invalidas = total_linhas
        resultado.linhas_validas = 0
    else:
        resultado.aprovado = True
        resultado.linhas_validas = total_linhas
        resultado.linhas_invalidas = 0

    resultado.df_resultado = df_validado
    return resultado


def simular_importacao_bling(
    df: pd.DataFrame,
    operacao: str,
    colunas_modelo: Optional[List[str]] = None,
    campos_obrigatorios_extras: Optional[List[str]] = None,
) -> Dict[str, object]:
    resultado = validar_dataframe_bling(
        df=df,
        operacao=operacao,
        colunas_modelo=colunas_modelo,
        campos_obrigatorios_extras=campos_obrigatorios_extras,
    )
    return resultado.to_dict()


