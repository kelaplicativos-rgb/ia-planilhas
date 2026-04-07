from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st


# ==========================================================
# BASE
# ==========================================================
def _to_dataframe(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if df is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(df)
    except Exception:
        return pd.DataFrame()


def _normalizar_nome_coluna(nome: Any) -> str:
    try:
        return (
            str(nome)
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
        )
    except Exception:
        return ""


def _safe_session_state_get(chave: str, default=None):
    try:
        return st.session_state.get(chave, default)
    except Exception:
        return default


# ==========================================================
# LOG
# ==========================================================
def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# 🔥 DETECTA COLUNA DEPÓSITO
# ==========================================================
def _detectar_coluna_deposito(df: pd.DataFrame):
    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        if "deposit" in nome or "depós" in nome or "deposito" in nome:
            return col
    return None


# ==========================================================
# 🔥 DETECTA COLUNA PREÇO
# ==========================================================
def _detectar_coluna_preco(df: pd.DataFrame):
    palavras = [
        "preço de venda",
        "preco de venda",
        "preço venda",
        "preco venda",
        "valor de venda",
        "preço",
        "preco",
        "valor",
        "valor unitario",
        "valor unitário",
    ]

    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        for p in palavras:
            if p in nome:
                return col

    return None


# ==========================================================
# 🔥 GARANTE DEPÓSITO FINAL
# ==========================================================
def _garantir_deposito(df: pd.DataFrame) -> pd.DataFrame:
    deposito = str(_safe_session_state_get("deposito_nome", "") or "").strip()

    if not deposito:
        return df

    df_saida = df.copy()
    col_dep = _detectar_coluna_deposito(df_saida)

    if col_dep:
        df_saida[col_dep] = deposito
    else:
        df_saida["Depósito"] = deposito

    return df_saida


# ==========================================================
# 🔥 GARANTE PREÇO FINAL
# ==========================================================
def _garantir_preco(df: pd.DataFrame) -> pd.DataFrame:
    bloqueios = _safe_session_state_get("bloquear_campos_auto", {})
    if not isinstance(bloqueios, dict) or not bloqueios.get("preco"):
        return df

    df_saida = df.copy()
    df_precificado = _safe_session_state_get("df_precificado")

    if not isinstance(df_precificado, pd.DataFrame) or df_precificado.empty:
        return df_saida

    col_preco_destino = _detectar_coluna_preco(df_saida)
    col_preco_origem = _detectar_coluna_preco(df_precificado)

    if not col_preco_destino or not col_preco_origem:
        return df_saida

    try:
        serie_origem = df_precificado[col_preco_origem].reset_index(drop=True)
        tamanho_destino = len(df_saida.index)

        if tamanho_destino <= 0:
            return df_saida

        if len(serie_origem) >= tamanho_destino:
            df_saida[col_preco_destino] = serie_origem.iloc[:tamanho_destino].values
        else:
            df_saida[col_preco_destino] = ""
            if len(serie_origem) > 0:
                df_saida.loc[
                    df_saida.index[: len(serie_origem)],
                    col_preco_destino,
                ] = serie_origem.values
    except Exception:
        pass

    return df_saida


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def _normalizar_valor_celula(valor: Any) -> Any:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    if isinstance(valor, (list, tuple, set)):
        return " | ".join("" if v is None else str(v) for v in valor)

    if isinstance(valor, dict):
        return " | ".join(f"{k}: {v}" for k, v in valor.items())

    return valor


def _normalizar_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    df_saida = _to_dataframe(df)

    if df_saida.empty:
        return df_saida

    df_saida = df_saida.copy()

    for col in df_saida.columns:
        df_saida[col] = df_saida[col].apply(_normalizar_valor_celula)

    return df_saida.fillna("")


# ==========================================================
# 🔥 GARANTIA DE ESTRUTURA
# ==========================================================
def _garantir_estrutura_modelo(df: pd.DataFrame) -> pd.DataFrame:
    df_saida = _to_dataframe(df)

    if df_saida.empty:
        return df_saida

    df_saida = df_saida.copy()
    df_saida.columns = [str(c).strip() for c in df_saida.columns]

    return df_saida


def _limpar_dataframe_lido(df: pd.DataFrame) -> pd.DataFrame:
    df_saida = _to_dataframe(df)

    if df_saida.empty:
        return df_saida

    df_saida = df_saida.copy()

    df_saida = df_saida.dropna(axis=1, how="all")
    df_saida = df_saida.dropna(axis=0, how="all")

    if df_saida.empty:
        return pd.DataFrame()

    colunas = []
    usados = set()

    for i, col in enumerate(df_saida.columns):
        nome = str(col).strip()

        if not nome or nome.lower().startswith("unnamed:"):
            nome = f"Coluna {i + 1}"

        nome_base = nome
        contador = 2
        while nome in usados:
            nome = f"{nome_base} ({contador})"
            contador += 1

        usados.add(nome)
        colunas.append(nome)

    df_saida.columns = colunas

    for col in df_saida.columns:
        try:
            df_saida[col] = df_saida[col].apply(
                lambda v: "" if v is None else str(v).strip()
            )
        except Exception:
            pass

    mascara_vazia = df_saida.apply(
        lambda row: all(str(v).strip() == "" for v in row.values), axis=1
    )
    df_saida = df_saida.loc[~mascara_vazia].copy()

    if df_saida.empty:
        return pd.DataFrame()

    df_saida.reset_index(drop=True, inplace=True)
    return df_saida


def _score_dataframe(df: pd.DataFrame) -> tuple[int, int, int]:
    """
    Score para escolher a melhor aba:
    1) mais linhas
    2) mais colunas
    3) mais cabeçalhos úteis
    """
    if df is None or df.empty:
        return (0, 0, 0)

    linhas = len(df)
    colunas = len(df.columns)

    cabecalhos_uteis = 0
    for c in df.columns:
        nome = str(c).strip().lower()
        if nome and not nome.startswith("coluna ") and not nome.startswith("unnamed:"):
            cabecalhos_uteis += 1

    return (linhas, colunas, cabecalhos_uteis)


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Planilha") -> bytes:
    df_saida = _garantir_estrutura_modelo(df)
    df_saida = _garantir_deposito(df_saida)
    df_saida = _garantir_preco(df_saida)
    df_saida = _normalizar_para_excel(df_saida)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()


def exportar_df_exato_para_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str = "Planilha",
) -> bytes:
    df_saida = _garantir_estrutura_modelo(df)
    df_saida = _garantir_deposito(df_saida)
    df_saida = _garantir_preco(df_saida)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()


def exportar_dataframe_para_excel(
    df: pd.DataFrame,
    sheet_name: str = "Planilha",
) -> bytes:
    """
    Compatibilidade com app.py, que tenta importar:
    exportar_dataframe_para_excel as _exportar_excel_robusto
    """
    return df_to_excel_bytes(df, sheet_name=sheet_name)


# ==========================================================
# LEITURA ROBUSTA
# ==========================================================
def _ler_csv_robusto(uploaded_file: Any) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252"]
    separadores = [None, ";", ",", "\t", "|"]

    melhor_df = pd.DataFrame()
    melhor_score = (0, 0, 0)

    for enc in encodings:
        for sep in separadores:
            try:
                if hasattr(uploaded_file, "seek"):
                    uploaded_file.seek(0)

                kwargs = {
                    "encoding": enc,
                    "dtype": str,
                    "keep_default_na": False,
                    "on_bad_lines": "skip",
                }

                if sep is None:
                    kwargs["sep"] = None
                    kwargs["engine"] = "python"
                else:
                    kwargs["sep"] = sep

                df = pd.read_csv(uploaded_file, **kwargs)
                df = _limpar_dataframe_lido(df)
                score = _score_dataframe(df)

                if score > melhor_score:
                    melhor_score = score
                    melhor_df = df

            except Exception:
                continue

    if not melhor_df.empty:
        return _garantir_estrutura_modelo(_normalizar_para_excel(melhor_df))

    return pd.DataFrame()


def _ler_excel_sheet_por_sheet(uploaded_file: Any) -> pd.DataFrame:
    melhor_df = pd.DataFrame()
    melhor_score = (0, 0, 0)

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        xls = pd.ExcelFile(uploaded_file)
        abas = xls.sheet_names or []

        for aba in abas:
            try:
                df = pd.read_excel(
                    xls,
                    sheet_name=aba,
                    dtype=str,
                )
                df = _limpar_dataframe_lido(df)
                score = _score_dataframe(df)

                _log_debug(
                    f"Excel analisado aba='{str(aba).strip()}' score={score} "
                    f"shape={df.shape if isinstance(df, pd.DataFrame) else (0, 0)}"
                )

                if score > melhor_score:
                    melhor_score = score
                    melhor_df = df

            except Exception as e:
                _log_debug(
                    f"Falha ao ler aba '{str(aba).strip()}': {e}",
                    "WARNING",
                )

    except Exception as e:
        _log_debug(f"Falha ao abrir workbook Excel: {e}", "ERROR")

    if not melhor_df.empty:
        return _garantir_estrutura_modelo(_normalizar_para_excel(melhor_df))

    return pd.DataFrame()


def ler_excel_robusto(uploaded_file: Any) -> pd.DataFrame:
    try:
        df = _ler_excel_sheet_por_sheet(uploaded_file)
        if not df.empty:
            return df
        return pd.DataFrame()
    except Exception as e:
        _log_debug(f"Erro ler_excel_robusto: {e}", "ERROR")
        return pd.DataFrame()


def ler_planilha_robusta(uploaded_file: Any) -> pd.DataFrame:
    try:
        nome = str(getattr(uploaded_file, "name", "") or "").lower().strip()

        if nome.endswith(".csv"):
            return _ler_csv_robusto(uploaded_file)

        if nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            return ler_excel_robusto(uploaded_file)

        df_excel = ler_excel_robusto(uploaded_file)
        if not df_excel.empty:
            return df_excel

        df_csv = _ler_csv_robusto(uploaded_file)
        if not df_csv.empty:
            return df_csv

        return pd.DataFrame()
    except Exception as e:
        _log_debug(f"Erro ler_planilha_robusta: {e}", "ERROR")
        return pd.DataFrame()
