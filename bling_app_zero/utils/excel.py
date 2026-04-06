from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def _to_dataframe(df: Any) -> pd.DataFrame:
    """
    Garante que a entrada seja um DataFrame válido.
    """
    if isinstance(df, pd.DataFrame):
        out = df.copy()
    elif df is None:
        out = pd.DataFrame()
    else:
        out = pd.DataFrame(df)

    return out


def _normalizar_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza o DataFrame antes da exportação:
    - preserva colunas e ordem
    - remove NaN/None
    - converte listas/dicts em texto
    """
    out = _to_dataframe(df)

    if out.empty:
        return out

    out = out.copy()

    for col in out.columns:
        out[col] = out[col].apply(_normalizar_valor_celula)

    out = out.fillna("")
    return out


def _normalizar_valor_celula(valor: Any) -> Any:
    """
    Ajusta valores problemáticos para gravação no Excel.
    """
    if valor is None:
        return ""

    if isinstance(valor, float) and pd.isna(valor):
        return ""

    if isinstance(valor, (list, tuple, set)):
        return " | ".join("" if v is None else str(v) for v in valor)

    if isinstance(valor, dict):
        partes = []
        for k, v in valor.items():
            partes.append(f"{k}: {'' if v is None else v}")
        return " | ".join(map(str, partes))

    return valor


def df_to_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str = "Planilha",
) -> bytes:
    """
    Exporta um DataFrame para bytes Excel (.xlsx).
    Compatível com imports já usados no projeto.
    """
    df_final = _normalizar_para_excel(df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_final.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()


def exportar_df_exato_para_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str = "Planilha",
) -> bytes:
    """
    Alias compatível com o nome usado por partes novas do projeto.
    """
    return df_to_excel_bytes(df=df, sheet_name=sheet_name)


def ler_planilha_excel(uploaded_file: Any) -> pd.DataFrame:
    """
    Lê XLSX/XLS/CSV com fallback simples.
    """
    nome = str(getattr(uploaded_file, "name", "") or "").lower()

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    if nome.endswith(".csv"):
        try:
            df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
        except Exception:
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
            df = pd.read_csv(
                uploaded_file,
                sep=";",
                dtype=str,
                keep_default_na=False,
                encoding="utf-8",
            )
    else:
        df = pd.read_excel(uploaded_file, dtype=str)

    return _normalizar_para_excel(df)


__all__ = [
    "df_to_excel_bytes",
    "exportar_df_exato_para_excel_bytes",
    "ler_planilha_excel",
]
