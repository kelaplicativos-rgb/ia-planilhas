# bling_app_zero/core/instant_scraper/self_healing.py

from __future__ import annotations

import re

import pandas as pd

from .stock_detector import enrich_dataframe_stock


MAPA_COLUNAS = {
    "nome": ["nome", "descricao", "descrição", "produto", "titulo", "title"],
    "preco": ["preco", "preço", "valor", "price"],
    "url_produto": ["url", "link", "href", "url_produto"],
    "imagem": ["imagem", "imagens", "foto", "image", "img"],
    "sku": ["sku", "codigo", "código", "cod", "referencia", "referência"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras"],
    "estoque": ["estoque", "stock", "disponibilidade", "availability", "saldo", "quantidade", "quantidade_real", "qtd", "qtde"],
}


def _txt(v: object) -> str:
    return " ".join(str(v or "").replace("\x00", " ").split()).strip()


def _norm(v: object) -> str:
    txt = _txt(v).lower()
    return txt.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))


def _count(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int(df[col].astype(str).str.strip().ne("").sum())


def _best_col(df: pd.DataFrame, termos: list[str]) -> str:
    melhor = ""
    score = 0
    termos_norm = [_norm(t) for t in termos]
    for col in df.columns:
        nome = _norm(col)
        if any(t in nome for t in termos_norm):
            atual = _count(df, col)
            if atual > score:
                melhor = str(col)
                score = atual
    return melhor


def _linha_texto(row: pd.Series) -> str:
    return " | ".join(_txt(v) for v in row.tolist())


def _extrair_preco(row: pd.Series) -> str:
    texto = _linha_texto(row)
    achados = re.findall(r"R\$\s*([0-9.,]+)", texto, flags=re.I)
    if not achados:
        return ""
    valor = achados[0]
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    return valor


def _extrair_sku(row: pd.Series) -> str:
    texto = _linha_texto(row)
    achado = re.search(r"(?:SKU|COD|CÓD|REF)[:\s-]*([A-Z0-9._/-]{3,40})", texto, flags=re.I)
    return _txt(achado.group(1)) if achado else ""


def _extrair_gtin(row: pd.Series) -> str:
    texto = _linha_texto(row)
    achado = re.search(r"\b\d{8,14}\b", texto)
    return achado.group(0) if achado else ""


def _extrair_nome(row: pd.Series) -> str:
    valores = [_txt(v) for v in row.tolist()]
    candidatos = [v for v in valores if len(v) >= 8 and not v.startswith("http") and "R$" not in v]
    if not candidatos:
        return ""
    candidatos.sort(key=len, reverse=True)
    return candidatos[0][:250]


def diagnosticar_dataframe(df: pd.DataFrame) -> dict:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"score": 0, "linhas": 0, "status": "sem_dados"}
    score = 20
    if len(df) >= 3:
        score += 10
    for col, peso in [
        ("nome", 25),
        ("preco", 25),
        ("url_produto", 10),
        ("imagem", 10),
        ("sku", 5),
        ("gtin", 5),
        ("estoque", 10),
        ("quantidade_real", 10),
    ]:
        if col in df.columns and _count(df, col) > 0:
            score += peso
    return {"score": min(score, 100), "linhas": int(len(df)), "status": "ok" if score >= 70 else "fraco"}


def auto_heal_dataframe(df: pd.DataFrame, url: str = "") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")

    renames = {}
    for destino, termos in MAPA_COLUNAS.items():
        if destino in base.columns:
            continue
        origem = _best_col(base, termos)
        if origem and origem not in renames:
            renames[origem] = destino
    if renames:
        base = base.rename(columns=renames)

    if "preco" not in base.columns or _count(base, "preco") == 0:
        base["preco"] = base.apply(_extrair_preco, axis=1)
    if "sku" not in base.columns or _count(base, "sku") == 0:
        base["sku"] = base.apply(_extrair_sku, axis=1)
    if "gtin" not in base.columns or _count(base, "gtin") == 0:
        base["gtin"] = base.apply(_extrair_gtin, axis=1)
    if "nome" not in base.columns or _count(base, "nome") == 0:
        base["nome"] = base.apply(_extrair_nome, axis=1)

    base = enrich_dataframe_stock(base)

    base = base.fillna("")
    base = base.loc[base.astype(str).apply(lambda row: any(v.strip() for v in row), axis=1)].copy()

    if "url_produto" in base.columns and "nome" in base.columns:
        base = base.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    elif "nome" in base.columns and "preco" in base.columns:
        base = base.drop_duplicates(subset=["nome", "preco"], keep="first")
    else:
        base = base.drop_duplicates(keep="first")

    return base.reset_index(drop=True)
