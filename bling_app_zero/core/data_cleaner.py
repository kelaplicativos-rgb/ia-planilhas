from __future__ import annotations

import re
import pandas as pd


def limpar_texto(valor: str) -> str:
    v = str(valor or "")
    v = re.sub(r"<[^>]+>", "", v)
    v = v.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", v).strip()


def limpar_preco(valor: str) -> str:
    v = str(valor or "")
    v = v.replace("R$", "").replace(" ", "")
    v = v.replace(".", "").replace(",", ".")
    return v if re.match(r"^\d+(\.\d+)?$", v) else ""


def limpar_gtin(valor: str) -> str:
    v = re.sub(r"\D", "", str(valor or ""))
    return v if len(v) in (8, 12, 13, 14) else ""


def limpar_imagens(valor: str) -> str:
    urls = re.split(r"[|,\s]+", str(valor or ""))
    urls = [u for u in urls if u.startswith("http")]
    return "|".join(urls[:10])


def aplicar_limpeza(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if "Descrição" in col:
            df[col] = df[col].apply(limpar_texto)

        if "Preço" in col:
            df[col] = df[col].apply(limpar_preco)

        if "GTIN" in col or "EAN" in col:
            df[col] = df[col].apply(limpar_gtin)

        if "imagem" in col.lower():
            df[col] = df[col].apply(limpar_imagens)

    return df
