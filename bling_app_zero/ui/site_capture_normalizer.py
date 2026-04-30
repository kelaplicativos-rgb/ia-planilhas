from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _txt(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def _norm(value: Any) -> str:
    text = _txt(value).lower()
    return text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))


def _first_existing(df: pd.DataFrame, names: list[str], partials: list[str] | None = None) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    partials = partials or []
    mapa = {_norm(c): str(c) for c in df.columns}
    for name in names:
        found = mapa.get(_norm(name))
        if found:
            return found
    partials_norm = [_norm(p) for p in partials]
    for col in df.columns:
        col_norm = _norm(col)
        if any(p and p in col_norm for p in partials_norm):
            return str(col)
    return ""


def _series(df: pd.DataFrame, col: str) -> pd.Series:
    if not col or col not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    return df[col].astype(str).fillna("").map(_txt).replace({"nan": "", "None": "", "none": ""})


def _clean_price(value: Any) -> str:
    raw = _txt(value)
    if not raw:
        return ""
    match = re.search(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{2})", raw, flags=re.I)
    if match:
        raw = match.group(1)
    else:
        match = re.search(r"-?\d+(?:[\.,]\d+)?", raw)
        raw = match.group(0) if match else ""
    if not raw:
        return ""
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    return raw


def _price_from_row(row: pd.Series) -> str:
    for value in row.tolist():
        price = _clean_price(value)
        if price:
            return price
    return ""


def _stock_from_row(row: pd.Series) -> str:
    joined = _norm(" | ".join(_txt(v) for v in row.tolist()))
    if any(x in joined for x in ["sem estoque", "indisponivel", "indisponível", "esgotado", "fora de estoque", "sold out"]):
        return "0"
    for pattern in [
        r"(?:estoque|saldo|quantidade|qtd|qtde|disponivel|disponibilidade)\s*[:\-]?\s*(\d{1,6})",
        r"(?:restam|resta)\s*(\d{1,6})",
        r"(\d{1,6})\s*(?:unidades|unidade|itens|item|pecas|peças)\s*(?:em estoque|disponiveis|disponíveis)",
    ]:
        match = re.search(pattern, joined, flags=re.I)
        if match:
            return str(max(int(match.group(1)), 0))
    # Produto de vitrine com preço/link é considerado disponível sem quantidade real.
    if any(x in joined for x in [" r$", "no pix", "cartao", "cartão", "comprar"]):
        return "1"
    return ""


def _looks_like_valid_product(row: pd.Series) -> bool:
    url = _txt(row.get("url_produto", row.get("URL", ""))).lower()
    name = _txt(row.get("nome", row.get("Descrição", row.get("descricao", ""))))
    price = _txt(row.get("preco", row.get("Preço", "")))
    sku = _txt(row.get("sku", row.get("Código", "")))
    gtin = _txt(row.get("gtin", row.get("GTIN", "")))
    desc = _txt(row.get("descricao", row.get("Descrição", "")))

    if name.lower() in {"produtos", "produto", "ver mais", "categorias", "categoria"} and not price and not sku and not gtin:
        return False
    if url.rstrip("/").endswith(("megacentereletronicos.com.br", "atacadum.com.br", "estoqui.com.br")) and not price and not sku and not gtin:
        return False
    return bool(price or sku or gtin or "/produto/" in url or len(desc) >= 30)


def normalizar_captura_site_para_bling(df: pd.DataFrame, deposito_nome: str = "") -> pd.DataFrame:
    """Cria colunas operacionais reais a partir da captura crua do scraper.

    A captura vem como url_produto/sku/descricao/nome/preco/estoque/gtin/imagem.
    Esta função preserva essas colunas e também cria aliases compatíveis com
    cadastro/estoque do Bling para o mapeamento e preview final não ficarem vazios.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [_txt(c) for c in base.columns]
    base = base.drop(columns=[c for c in base.columns if str(c).lower().startswith("unnamed:") or str(c).lower() in {"index", "level_0"}], errors="ignore")

    for col in base.columns:
        base[col] = base[col].astype(str).fillna("").map(_txt)

    url_col = _first_existing(base, ["url_produto", "URL", "Link", "href"], ["url", "link"])
    sku_col = _first_existing(base, ["sku", "Código", "codigo", "Código produto *", "Codigo produto *"], ["sku", "codigo", "código", "cod"])
    desc_col = _first_existing(base, ["descricao", "Descrição", "Descrição Produto", "nome", "Nome"], ["descricao", "descrição", "nome", "produto"])
    nome_col = _first_existing(base, ["nome", "Nome", "descricao", "Descrição"], ["nome", "descricao", "descrição"])
    preco_col = _first_existing(base, ["preco", "Preço", "valor", "Preço unitário (OBRIGATÓRIO)"], ["preco", "preço", "valor"])
    estoque_col = _first_existing(base, ["quantidade_real", "estoque", "Quantidade", "Balanço (OBRIGATÓRIO)"], ["quantidade", "estoque", "balanco", "balanço", "saldo"])
    gtin_col = _first_existing(base, ["gtin", "GTIN", "EAN", "GTIN **"], ["gtin", "ean", "barras"])
    imagem_col = _first_existing(base, ["imagem", "imagens", "Imagem", "Imagens"], ["imagem", "image", "foto"])

    codigo = _series(base, sku_col)
    gtin = _series(base, gtin_col)
    codigo = codigo.where(codigo.ne(""), gtin)

    nome = _series(base, nome_col)
    descricao = _series(base, desc_col)
    descricao = descricao.where(descricao.ne(""), nome)
    nome = nome.where(nome.ne(""), descricao)

    preco = _series(base, preco_col).map(_clean_price)
    if preco.eq("").any():
        preco_linha = base.apply(_price_from_row, axis=1)
        preco = preco.where(preco.ne(""), preco_linha)

    estoque = _series(base, estoque_col)
    estoque = estoque.map(lambda x: re.search(r"\d+", x).group(0) if re.search(r"\d+", x) else "")
    if estoque.eq("").any():
        estoque_linha = base.apply(_stock_from_row, axis=1)
        estoque = estoque.where(estoque.ne(""), estoque_linha)

    base["URL"] = _series(base, url_col)
    base["Código"] = codigo
    base["Codigo produto *"] = codigo
    base["SKU"] = codigo
    base["Descrição"] = descricao
    base["Descrição Produto"] = descricao
    base["Descrição Curta"] = nome.where(nome.ne(""), descricao)
    base["Nome"] = nome.where(nome.ne(""), descricao)
    base["Preço unitário (OBRIGATÓRIO)"] = preco
    base["Preço de Custo"] = preco
    base["Preço"] = preco
    base["Balanço (OBRIGATÓRIO)"] = estoque.where(estoque.ne(""), "0")
    base["Estoque"] = base["Balanço (OBRIGATÓRIO)"]
    base["GTIN"] = gtin
    base["GTIN **"] = gtin
    base["Imagens"] = _series(base, imagem_col)
    base["Imagem"] = base["Imagens"]
    if deposito_nome:
        base["Deposito (OBRIGATÓRIO)"] = _txt(deposito_nome)
        base["Depósito"] = _txt(deposito_nome)

    base = base[base.apply(_looks_like_valid_product, axis=1)].copy()

    preferidas = [
        "Código", "Codigo produto *", "SKU", "Descrição", "Descrição Produto", "Descrição Curta", "Nome",
        "Preço unitário (OBRIGATÓRIO)", "Preço de Custo", "Preço", "Balanço (OBRIGATÓRIO)", "Estoque",
        "Deposito (OBRIGATÓRIO)", "Depósito", "GTIN", "GTIN **", "URL", "Imagens", "Imagem",
    ]
    existentes = [c for c in preferidas if c in base.columns]
    restantes = [c for c in base.columns if c not in existentes]
    base = base[existentes + restantes]

    if "URL" in base.columns and base["URL"].astype(str).str.strip().ne("").any():
        base = base.drop_duplicates(subset=["URL"], keep="first")
    elif "Código" in base.columns and base["Código"].astype(str).str.strip().ne("").any():
        base = base.drop_duplicates(subset=["Código"], keep="first")
    else:
        base = base.drop_duplicates(keep="first")

    return base.reset_index(drop=True).fillna("")
