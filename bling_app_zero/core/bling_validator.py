from __future__ import annotations

import re
import pandas as pd


def validar_df_bling(df: pd.DataFrame) -> list[str]:
    erros: list[str] = []

    if df is None or df.empty:
        return ["A planilha final está vazia."]

    if "Descrição" in df.columns and not df["Descrição"].astype(str).str.strip().any():
        erros.append("Descrição está vazia. O Bling precisa de descrição do produto.")

    preco_cols = [c for c in df.columns if "Preço" in c]
    if preco_cols:
        col = preco_cols[0]
        validos = df[col].astype(str).str.match(r"^\d+(\.\d+)?$", na=False)
        if not validos.any():
            erros.append(f"Nenhum preço válido encontrado em {col}.")

    for col in df.columns:
        if "GTIN" in col or "EAN" in col:
            invalidos = df[col].astype(str).apply(lambda v: bool(v.strip()) and len(re.sub(r"\D", "", v)) not in (8, 12, 13, 14))
            if invalidos.any():
                erros.append(f"Existem GTIN/EAN inválidos em {col}.")

    return erros
