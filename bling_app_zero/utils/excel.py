from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


# ==========================================================
# BASE
# ==========================================================
def _to_dataframe(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if df is None:
        return pd.DataFrame()
    return pd.DataFrame(df)


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def _normalizar_valor_celula(valor: Any) -> Any:

    if valor is None:
        return ""

    if isinstance(valor, float) and pd.isna(valor):
        return ""

    if isinstance(valor, (list, tuple, set)):
        return " | ".join("" if v is None else str(v) for v in valor)

    if isinstance(valor, dict):
        return " | ".join(f"{k}: {v}" for k, v in valor.items())

    return valor


def _normalizar_para_excel(df: pd.DataFrame) -> pd.DataFrame:

    df = _to_dataframe(df)

    if df.empty:
        return df

    df = df.copy()

    for col in df.columns:
        df[col] = df[col].apply(_normalizar_valor_celula)

    return df.fillna("")


# ==========================================================
# 🔥 GARANTIA DE ESTRUTURA (NÃO PERDER COLUNAS)
# ==========================================================
def _garantir_estrutura_modelo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que nenhuma coluna seja perdida e mantém ordem.
    """
    df = _to_dataframe(df)

    if df.empty:
        return df

    # força colunas como string
    df.columns = [str(c) for c in df.columns]

    return df


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Planilha") -> bytes:

    # 🔥 IMPORTANTE: preservar estrutura antes de normalizar
    df = _garantir_estrutura_modelo(df)

    # normalização leve (sem quebrar estrutura)
    df = _normalizar_para_excel(df)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()


def exportar_df_exato_para_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str = "Planilha"
) -> bytes:
    """
    Exporta EXATAMENTE como está (sem alterar estrutura)
    """
    df = _garantir_estrutura_modelo(df)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()


# ==========================================================
# 🔥 LEITURA ROBUSTA
# ==========================================================
def ler_planilha_excel(uploaded_file: Any) -> pd.DataFrame:

    nome = str(getattr(uploaded_file, "name", "") or "").lower()

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    # =========================
    # CSV ROBUSTO
    # =========================
    if nome.endswith(".csv"):

        encodings = ["utf-8", "latin1", "cp1252"]
        separadores = [",", ";", "\t"]

        for enc in encodings:
            for sep in separadores:
                try:
                    if hasattr(uploaded_file, "seek"):
                        uploaded_file.seek(0)

                    df = pd.read_csv(
                        uploaded_file,
                        sep=sep,
                        encoding=enc,
                        dtype=str,
                        keep_default_na=False,
                    )

                    if df is not None and not df.empty:
                        return _garantir_estrutura_modelo(_normalizar_para_excel(df))

                except Exception:
                    continue

        return pd.DataFrame()

    # =========================
    # EXCEL ROBUSTO
    # =========================
    try:
        df = pd.read_excel(uploaded_file, dtype=str)

        if df is not None and not df.empty:
            return _garantir_estrutura_modelo(_normalizar_para_excel(df))

    except Exception:
        pass

    # fallback total
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
    "ler_planilha_excel",
]
