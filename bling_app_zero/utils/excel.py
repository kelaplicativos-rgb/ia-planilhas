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
        return str(nome).strip().lower().replace("_", " ")
    except Exception:
        return ""


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
    deposito = str(st.session_state.get("deposito_nome", "") or "").strip()

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
    bloqueios = st.session_state.get("bloquear_campos_auto", {})
    if not isinstance(bloqueios, dict) or not bloqueios.get("preco"):
        return df

    df_saida = df.copy()
    df_precificado = st.session_state.get("df_precificado")

    if not isinstance(df_precificado, pd.DataFrame) or df_precificado.empty:
        return df_saida

    col_preco_destino = _detectar_coluna_preco(df_saida)
    col_preco_origem = _detectar_coluna_preco(df_precificado)

    if not col_preco_destino or not col_preco_origem:
        return df_saida

    try:
        serie_origem = df_precificado[col_preco_origem].reset_index(drop=True)
        tamanho_destino = len(df_saida.index)

        if len(serie_origem) >= tamanho_destino:
            df_saida[col_preco_destino] = serie_origem.iloc[:tamanho_destino].values
        else:
            df_saida[col_preco_destino] = ""
            df_saida.loc[: len(serie_origem) - 1, col_preco_destino] = serie_origem.values
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
    df_saida.columns = [str(c) for c in df_saida.columns]

    return df_saida


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


def exportar_dataframe_para_excel(df: pd.DataFrame, sheet_name: str = "Planilha") -> bytes:
    """
    Compatibilidade com app.py, que tenta importar:
    exportar_dataframe_para_excel as _exportar_excel_robusto
    """
    return df_to_excel_bytes(df, sheet_name=sheet_name)


# ==========================================================
# LEITURA ROBUSTA
# ==========================================================
def ler_planilha_excel(uploaded_file: Any) -> pd.DataFrame:
    nome = str(getattr(uploaded_file, "name", "") or "").lower()

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    if nome.endswith(".csv"):
        encodings = ["utf-8-sig", "utf-8", "latin1", "cp1252"]
        separadores = [None, ",", ";", "\t"]

        for enc in encodings:
            for sep in separadores:
                try:
                    if hasattr(uploaded_file, "seek"):
                        uploaded_file.seek(0)

                    kwargs = {
                        "encoding": enc,
                        "dtype": str,
                        "keep_default_na": False,
                    }

                    if sep is None:
                        kwargs["sep"] = None
                        kwargs["engine"] = "python"
                    else:
                        kwargs["sep"] = sep

                    df = pd.read_csv(uploaded_file, **kwargs)

                    if df is not None and not df.empty:
                        return _garantir_estrutura_modelo(_normalizar_para_excel(df))

                except Exception:
                    continue

        return pd.DataFrame()

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        df = pd.read_excel(uploaded_file, dtype=str)

        if df is not None and not df.empty:
            return _garantir_estrutura_modelo(_normalizar_para_excel(df))

    except Exception:
        pass

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        df = pd.read_excel(uploaded_file)

        return _garantir_estrutura_modelo(_normalizar_para_excel(df))

    except Exception:
        return pd.DataFrame()


__all__ = [
    "df_to_excel_bytes",
    "exportar_df_exato_para_excel_bytes",
    "exportar_dataframe_para_excel",
    "ler_planilha_excel",
]
