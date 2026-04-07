from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

# ==========================================================
# IMPORTS OPCIONAIS / BLINDAGEM
# ==========================================================
try:
    from bling_app_zero.utils.excel import (
        exportar_dataframe_para_excel as _exportar_excel_robusto,
    )
except Exception:
    _exportar_excel_robusto = None

try:
    from bling_app_zero.utils.excel import (
        df_to_excel_bytes as _df_to_excel_bytes_utils,
    )
except Exception:
    _df_to_excel_bytes_utils = None

try:
    from bling_app_zero.utils.excel import ler_planilha_arquivo as _ler_planilha_arquivo_utils
except Exception:
    _ler_planilha_arquivo_utils = None

try:
    from bling_app_zero.utils.excel import ler_planilha as _ler_planilha_utils
except Exception:
    _ler_planilha_utils = None

try:
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_df
except Exception:
    aplicar_validacao_gtin_df = None


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def _safe_text(value: Any) -> str:
    try:
        if value is None:
            return ""
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _normalizar_nome_coluna(nome: Any) -> str:
    return (
        _safe_text(nome)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("  ", " ")
    )


def _colunas_possiveis_gtin(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    candidatas: list[str] = []
    chaves = [
        "gtin",
        "ean",
        "código de barras",
        "codigo de barras",
        "cod barras",
        "cod. barras",
        "gtin/ean",
        "ean/gtin",
        "gtin tribut",
        "ean tribut",
    ]

    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        if any(chave in nome for chave in chaves):
            candidatas.append(col)

    return candidatas


def _ler_csv_fallback(arquivo) -> pd.DataFrame:
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ",", "encoding": "latin-1"},
    ]

    ultimo_erro = None

    for kwargs in tentativas:
        try:
            if hasattr(arquivo, "seek"):
                arquivo.seek(0)
            df = pd.read_csv(arquivo, **kwargs)
            if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
                return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(f"Falha ao ler CSV: {ultimo_erro}")


# ==========================================================
# LEITURA DE PLANILHA
# ==========================================================
def ler_planilha_segura(arquivo) -> pd.DataFrame:
    """
    Lê xlsx/xls/xlsm/xlsb/csv com fallback seguro.
    """
    if arquivo is None:
        return pd.DataFrame()

    nome = str(getattr(arquivo, "name", "") or "").lower().strip()

    try:
        if _ler_planilha_arquivo_utils is not None:
            try:
                if hasattr(arquivo, "seek"):
                    arquivo.seek(0)
                df = _ler_planilha_arquivo_utils(arquivo)
                if isinstance(df, pd.DataFrame):
                    return df
            except Exception as e:
                log_debug(f"Falha em _ler_planilha_arquivo_utils: {e}", "ERRO")

        if _ler_planilha_utils is not None:
            try:
                if hasattr(arquivo, "seek"):
                    arquivo.seek(0)
                df = _ler_planilha_utils(arquivo)
                if isinstance(df, pd.DataFrame):
                    return df
            except Exception as e:
                log_debug(f"Falha em _ler_planilha_utils: {e}", "ERRO")

        if nome.endswith(".csv"):
            return _ler_csv_fallback(arquivo)

        if hasattr(arquivo, "seek"):
            arquivo.seek(0)

        return pd.read_excel(arquivo)
    except Exception as e:
        log_debug(f"Erro ao ler planilha '{nome}': {e}", "ERRO")
        return pd.DataFrame()


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def _exportar_excel_fallback(df: pd.DataFrame) -> bytes:
    df_saida = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, sheet_name="Planilha", index=False)

    output.seek(0)
    return output.getvalue()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    if _df_to_excel_bytes_utils is not None:
        try:
            retorno = _df_to_excel_bytes_utils(df)
            if isinstance(retorno, bytes):
                return retorno
            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception as e:
            log_debug(f"Falha em _df_to_excel_bytes_utils: {e}", "ERRO")

    if _exportar_excel_robusto is not None:
        try:
            retorno = _exportar_excel_robusto(df)
            if isinstance(retorno, bytes):
                return retorno
            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception as e:
            log_debug(f"Falha em _exportar_excel_robusto: {e}", "ERRO")

    return _exportar_excel_fallback(df)


# ==========================================================
# GTIN
# ==========================================================
def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    df_saida = df.copy()

    if aplicar_validacao_gtin_df is None:
        for col in df_saida.columns:
            nome = _normalizar_nome_coluna(col)
            if (
                "gtin" in nome
                or "ean" in nome
                or "codigo de barras" in nome
                or "código de barras" in nome
            ):
                df_saida[col] = df_saida[col].apply(
                    lambda x: "".join(ch for ch in str(x or "") if ch.isdigit())
                )
                df_saida[col] = df_saida[col].apply(
                    lambda x: x if len(str(x)) in [8, 12, 13, 14] else ""
                )
        return df_saida

    try:
        colunas_gtin = _colunas_possiveis_gtin(df_saida)

        for col in colunas_gtin:
            try:
                df_saida, logs_gtin = aplicar_validacao_gtin_df(df_saida, col)
                if isinstance(logs_gtin, list):
                    for linha in logs_gtin[-20:]:
                        log_debug(str(linha), "INFO")
            except Exception as e:
                log_debug(f"Falha ao validar GTIN na coluna '{col}': {e}", "ERRO")

        return df_saida
    except Exception as e:
        log_debug(f"Erro geral ao limpar GTIN inválido: {e}", "ERRO")
        return df.copy()


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _obter_campos_faltando_de_estado() -> list[str]:
    candidatos = [
        "campos_obrigatorios_faltando",
        "faltando_obrigatorios",
        "erros_campos_obrigatorios",
        "validacao_campos_obrigatorios",
    ]

    faltando: list[str] = []

    for chave in candidatos:
        valor = st.session_state.get(chave)

        if isinstance(valor, dict):
            for k, v in valor.items():
                if v:
                    faltando.append(str(k).strip())

        elif isinstance(valor, (list, tuple, set)):
            faltando.extend([str(x).strip() for x in valor if str(x).strip()])

        elif isinstance(valor, str) and valor.strip():
            faltando.append(valor.strip())

    vistos = set()
    saida: list[str] = []
    for item in faltando:
        if item and item not in vistos:
            vistos.add(item)
            saida.append(item)

    return saida


def validar_campos_obrigatorios(df: pd.DataFrame):
    try:
        if not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) == 0:
            return ["Nenhum dado final disponível para download."]

        faltando_estado = _obter_campos_faltando_de_estado()
        if faltando_estado:
            return faltando_estado

        obrigatorios = st.session_state.get("colunas_obrigatorias_download")
        if isinstance(obrigatorios, (list, tuple, set)) and obrigatorios:
            faltando: list[str] = []

            for col in obrigatorios:
                col = str(col).strip()
                if not col:
                    continue

                if col not in df.columns:
                    faltando.append(col)
                    continue

                serie = df[col]
                preenchidos = serie.astype(str).str.strip().replace(
                    {"nan": "", "None": "", "null": ""}
                )
                if (preenchidos != "").sum() == 0:
                    faltando.append(col)

            if faltando:
                return faltando

        return True
    except Exception as e:
        log_debug(f"Erro interno na validação de obrigatórios: {e}", "ERRO")
        return True
