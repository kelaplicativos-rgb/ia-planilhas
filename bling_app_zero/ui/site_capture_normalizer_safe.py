from __future__ import annotations

import re
from typing import Any

import pandas as pd

try:
    from bling_app_zero.ui.site_product_enricher import (
        infer_additional_info,
        infer_brand,
        infer_category,
        infer_department,
        infer_ncm,
        infer_tags,
    )
except Exception:
    def infer_brand(description: Any, existing: Any = "") -> str:
        return str(existing or "").strip()

    def infer_category(description: Any, existing: Any = "") -> str:
        return str(existing or "").strip()

    def infer_ncm(description: Any, existing: Any = "") -> str:
        return re.sub(r"\D+", "", str(existing or ""))[:8]

    def infer_tags(description: Any) -> str:
        return ""

    def infer_department(category: Any) -> str:
        return str(category or "").split(">")[0].strip()

    def infer_additional_info(description: Any, ncm: str, category: str, brand: str) -> str:
        return ""


BLING_CADASTRO_COLUMNS = [
    "ID", "Código", "Descrição", "Unidade", "NCM", "Origem", "Preço", "Valor IPI fixo", "Observações",
    "Situação", "Estoque", "Preço de custo", "Cód no fornecedor", "Fornecedor", "Localização", "Estoque maximo",
    "Estoque minimo", "Peso líquido (Kg)", "Peso bruto (Kg)", "GTIN/EAN", "GTIN/EAN da embalagem",
    "Largura do Produto", "Altura do Produto", "Profundidade do produto", "Data Validade",
    "Descrição do Produto no Fornecedor", "Descrição Complementar", "Itens p/ caixa", "Produto Variação",
    "Tipo Produção", "Classe de enquadramento do IPI", "Código da lista de serviços", "Tipo do item",
    "Grupo de Tags/Tags", "Tributos", "Código Pai", "Código Integração", "Grupo de produtos", "Marca", "CEST",
    "Volumes", "Descrição Curta", "Cross-Docking", "URL Imagens Externas", "Link Externo",
    "Meses Garantia no Fornecedor", "Clonar dados do pai", "Condição do produto", "Frete Grátis", "Número FCI",
    "Vídeo", "Departamento", "Unidade de medida", "Preço de compra", "Valor base ICMS ST para retenção",
    "Valor ICMS ST para retenção", "Valor ICMS próprio do substituto", "Categoria do produto", "Informações Adicionais",
]

BLING_ESTOQUE_COLUMNS = [
    "ID", "Código", "Descrição", "Balanço (OBRIGATÓRIO)", "Depósito (OBRIGATÓRIO)",
    "Preço unitário (OBRIGATÓRIO)", "Preço de Custo", "GTIN", "URL", "Imagens",
]


def _txt(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def _norm(value: Any) -> str:
    return _txt(value).lower().translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))


def _drop_artificial(df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [
        col for col in df.columns
        if str(col).lower().startswith("unnamed:") or str(col).lower() in {"index", "level_0"}
    ]
    return df.drop(columns=drop_cols, errors="ignore")


def _first_col(df: pd.DataFrame, exact: list[str], partial: list[str]) -> str:
    mapa = {_norm(c): str(c) for c in df.columns}
    for item in exact:
        found = mapa.get(_norm(item))
        if found:
            return found
    partial_norm = [_norm(p) for p in partial]
    for col in df.columns:
        name = _norm(col)
        if any(p and p in name for p in partial_norm):
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
    money = re.search(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{2})", raw, re.I)
    if money:
        raw = money.group(1)
    else:
        number = re.search(r"-?\d+(?:[\.,]\d+)?", raw)
        raw = number.group(0) if number else ""
    if not raw:
        return ""
    return raw.replace(".", "").replace(",", ".") if "," in raw else raw


def _clean_description(value: Any) -> str:
    text = _txt(value)
    text = re.sub(r"^\s*esgotado\s+", "", text, flags=re.I)
    text = re.sub(r"\bC[ÓO]D\s*[:\-]?\s*\d{3,20}\b", "", text, flags=re.I)
    text = re.sub(r"R\$\s*[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}", "", text, flags=re.I)
    text = re.sub(r"R\$\s*[0-9]+,[0-9]{2}", "", text, flags=re.I)
    text = re.sub(r"\b(no pix|ou|cartao|cartão|no cartão)\b", "", text, flags=re.I)
    return _txt(text)[:250]


def _price_from_row(row: pd.Series) -> str:
    for value in row.tolist():
        price = _clean_price(value)
        if price:
            return price
    return ""


def _stock_from_row(row: pd.Series) -> str:
    joined = _norm(" | ".join(_txt(v) for v in row.tolist()))
    if any(x in joined for x in ["sem estoque", "indisponivel", "esgotado", "fora de estoque", "sold out"]):
        return "0"
    for pattern in [r"(?:estoque|saldo|quantidade|qtd|qtde)\s*[:\-]?\s*(\d{1,6})", r"(?:restam|resta)\s*(\d{1,6})"]:
        match = re.search(pattern, joined, flags=re.I)
        if match:
            return str(max(int(match.group(1)), 0))
    return "1" if any(x in joined for x in [" r$", "no pix", "cartao", "cartão", "comprar"]) else "0"


def _fields(df: pd.DataFrame) -> dict[str, pd.Series | pd.DataFrame]:
    base = _drop_artificial(df.copy().fillna(""))
    base.columns = [_txt(c) for c in base.columns]
    for col in base.columns:
        base[col] = base[col].astype(str).fillna("").map(_txt)

    url_col = _first_col(base, ["url_produto", "URL", "Link Externo", "Link", "href"], ["url", "link"])
    sku_col = _first_col(base, ["sku", "Código", "codigo", "Código produto *", "Codigo produto *", "Cód no fornecedor"], ["sku", "codigo", "código", "cod"])
    desc_col = _first_col(base, ["descricao", "Descrição", "Descrição Produto", "Descrição do Produto no Fornecedor", "nome", "Nome"], ["descricao", "descrição", "nome", "produto"])
    price_col = _first_col(base, ["preco", "Preço", "valor", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo"], ["preco", "preço", "valor"])
    stock_col = _first_col(base, ["quantidade_real", "estoque", "Estoque", "Quantidade", "Balanço (OBRIGATÓRIO)"], ["quantidade", "estoque", "balanco", "balanço", "saldo"])
    gtin_col = _first_col(base, ["gtin", "GTIN", "GTIN/EAN", "EAN", "GTIN **"], ["gtin", "ean", "barras"])
    image_col = _first_col(base, ["imagem", "imagens", "Imagem", "Imagens", "URL Imagens Externas"], ["imagem", "image", "foto"])
    brand_col = _first_col(base, ["marca", "Marca", "brand"], ["marca", "brand"])
    category_col = _first_col(base, ["categoria", "Categoria", "Categoria do produto"], ["categoria", "category"])
    ncm_col = _first_col(base, ["NCM", "ncm"], ["ncm"])

    gtin = _series(base, gtin_col)
    code_source = _series(base, sku_col)
    code = code_source.where(code_source.ne(""), gtin)
    desc = _series(base, desc_col).map(_clean_description)
    price = _series(base, price_col).map(_clean_price)
    price = price.where(price.ne(""), base.apply(_price_from_row, axis=1))
    stock = _series(base, stock_col).map(lambda x: re.search(r"\d+", x).group(0) if re.search(r"\d+", x) else "")
    stock = stock.where(stock.ne(""), base.apply(_stock_from_row, axis=1))

    brand = pd.Series([infer_brand(d, m) for d, m in zip(desc, _series(base, brand_col))], index=base.index)
    category = pd.Series([infer_category(d, c) for d, c in zip(desc, _series(base, category_col))], index=base.index)
    ncm = pd.Series([infer_ncm(d, n) for d, n in zip(desc, _series(base, ncm_col))], index=base.index)
    tags = desc.map(infer_tags)
    department = category.map(infer_department)
    info = pd.Series([infer_additional_info(d, n, c, m) for d, n, c, m in zip(desc, ncm, category, brand)], index=base.index)

    return {
        "base": base,
        "codigo": code,
        "descricao": desc,
        "preco": price,
        "estoque": stock,
        "gtin": gtin,
        "url": _series(base, url_col),
        "imagem": _series(base, image_col),
        "marca": brand,
        "categoria": category,
        "ncm": ncm,
        "tags": tags,
        "departamento": department,
        "info": info,
    }


def _valid_product(row: pd.Series) -> bool:
    code = _txt(row.get("Código", ""))
    desc = _txt(row.get("Descrição", ""))
    price = _txt(row.get("Preço", row.get("Preço unitário (OBRIGATÓRIO)", "")))
    gtin = _txt(row.get("GTIN/EAN", row.get("GTIN", "")))
    return bool(code or gtin or price or len(desc) >= 12)


def normalizar_captura_site_para_bling(df: pd.DataFrame, deposito_nome: str = "", tipo_operacao: str = "cadastro") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    fields = _fields(df)
    base = fields["base"]
    operacao = _norm(tipo_operacao) or "cadastro"

    if operacao == "estoque":
        out = pd.DataFrame("", index=base.index, columns=BLING_ESTOQUE_COLUMNS)
        out["Código"] = fields["codigo"]
        out["Descrição"] = fields["descricao"]
        out["Balanço (OBRIGATÓRIO)"] = fields["estoque"]
        out["Depósito (OBRIGATÓRIO)"] = _txt(deposito_nome)
        out["Preço unitário (OBRIGATÓRIO)"] = fields["preco"]
        out["Preço de Custo"] = fields["preco"]
        out["GTIN"] = fields["gtin"]
        out["URL"] = fields["url"]
        out["Imagens"] = fields["imagem"]
    else:
        out = pd.DataFrame("", index=base.index, columns=BLING_CADASTRO_COLUMNS)
        out["Código"] = fields["codigo"]
        out["Descrição"] = fields["descricao"]
        out["Unidade"] = "PC"
        out["NCM"] = fields["ncm"]
        out["Origem"] = "1"
        out["Preço"] = fields["preco"]
        out["Situação"] = "Ativo"
        out["Estoque"] = fields["estoque"]
        out["Preço de custo"] = fields["preco"]
        out["Cód no fornecedor"] = fields["codigo"]
        out["GTIN/EAN"] = fields["gtin"]
        out["GTIN/EAN da embalagem"] = fields["gtin"]
        out["Descrição do Produto no Fornecedor"] = fields["descricao"]
        out["Descrição Complementar"] = fields["descricao"]
        out["Tipo do item"] = "Produto"
        out["Grupo de Tags/Tags"] = fields["tags"]
        out["Marca"] = fields["marca"]
        out["Descrição Curta"] = fields["descricao"]
        out["URL Imagens Externas"] = fields["imagem"]
        out["Link Externo"] = fields["url"]
        out["Condição do produto"] = "Novo"
        out["Departamento"] = fields["departamento"]
        out["Unidade de medida"] = "PC"
        out["Preço de compra"] = fields["preco"]
        out["Categoria do produto"] = fields["categoria"]
        out["Informações Adicionais"] = fields["info"]

    out = out[out.apply(_valid_product, axis=1)].copy()
    if "Código" in out.columns and out["Código"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["Código"], keep="first")
    elif "Link Externo" in out.columns and out["Link Externo"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["Link Externo"], keep="first")
    elif "URL" in out.columns and out["URL"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["URL"], keep="first")
    return out.reset_index(drop=True).fillna("")
