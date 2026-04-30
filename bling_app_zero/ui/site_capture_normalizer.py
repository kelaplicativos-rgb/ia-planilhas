from __future__ import annotations

import re
from typing import Any

import pandas as pd


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
    text = _txt(value).lower()
    return text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))


def _first_existing(df: pd.DataFrame, names: list[str], partials: list[str] | None = None) -> str:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
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
    if any(x in joined for x in ["sem estoque", "indisponivel", "esgotado", "fora de estoque", "sold out"]):
        return "0"
    for pattern in [
        r"(?:estoque|saldo|quantidade|qtd|qtde|disponivel|disponibilidade)\s*[:\-]?\s*(\d{1,6})",
        r"(?:restam|resta)\s*(\d{1,6})",
        r"(\d{1,6})\s*(?:unidades|unidade|itens|item|pecas|peças)\s*(?:em estoque|disponiveis|disponíveis)",
    ]:
        match = re.search(pattern, joined, flags=re.I)
        if match:
            return str(max(int(match.group(1)), 0))
    if any(x in joined for x in [" r$", "no pix", "cartao", "cartão", "comprar"]):
        return "1"
    return ""


def _clean_description(value: Any) -> str:
    text = _txt(value)
    text = re.sub(r"^\s*esgotado\s+", "", text, flags=re.I)
    text = re.sub(r"\bC[ÓO]D\s*[:\-]?\s*\d{6,20}\b", "", text, flags=re.I)
    text = re.sub(r"R\$\s*[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}", "", text, flags=re.I)
    text = re.sub(r"R\$\s*[0-9]+,[0-9]{2}", "", text, flags=re.I)
    text = re.sub(r"\b\d+\s*%\b", "", text)
    text = re.sub(r"\b(no pix|ou|cartao|cartão|no cartão)\b", "", text, flags=re.I)
    text = _txt(text)
    return text[:250]


def _is_valid_product(row: pd.Series) -> bool:
    codigo = _txt(row.get("Código", ""))
    descricao = _txt(row.get("Descrição", ""))
    preco = _txt(row.get("Preço", ""))
    gtin = _txt(row.get("GTIN/EAN", row.get("GTIN", "")))
    url = _txt(row.get("Link Externo", row.get("URL", ""))).lower()
    if descricao.lower() in {"produtos", "produto", "ver mais", "categorias", "categoria"} and not preco and not codigo and not gtin:
        return False
    if url.rstrip("/").endswith(("megacentereletronicos.com.br", "atacadum.com.br", "estoqui.com.br")) and not preco and not codigo and not gtin:
        return False
    return bool(codigo or gtin or preco or "/produto/" in url or len(descricao) >= 12)


def _extract_fields(df: pd.DataFrame) -> dict[str, pd.Series]:
    base = df.copy().fillna("")
    base.columns = [_txt(c) for c in base.columns]
    base = base.drop(columns=[c for c in base.columns if str(c).lower().startswith("unnamed:") or str(c).lower() in {"index", "level_0"}], errors="ignore")
    for col in base.columns:
        base[col] = base[col].astype(str).fillna("").map(_txt)

    url_col = _first_existing(base, ["url_produto", "URL", "Link Externo", "Link", "href"], ["url", "link"])
    sku_col = _first_existing(base, ["sku", "Código", "codigo", "Código produto *", "Codigo produto *", "Cód no fornecedor"], ["sku", "codigo", "código", "cod"])
    desc_col = _first_existing(base, ["descricao", "Descrição", "Descrição Produto", "Descrição do Produto no Fornecedor", "nome", "Nome"], ["descricao", "descrição", "nome", "produto"])
    nome_col = _first_existing(base, ["nome", "Nome", "Descrição Curta", "descricao", "Descrição"], ["nome", "descricao", "descrição"])
    preco_col = _first_existing(base, ["preco", "Preço", "valor", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo"], ["preco", "preço", "valor"])
    estoque_col = _first_existing(base, ["quantidade_real", "estoque", "Estoque", "Quantidade", "Balanço (OBRIGATÓRIO)"], ["quantidade", "estoque", "balanco", "balanço", "saldo"])
    gtin_col = _first_existing(base, ["gtin", "GTIN", "GTIN/EAN", "EAN", "GTIN **"], ["gtin", "ean", "barras"])
    imagem_col = _first_existing(base, ["imagem", "imagens", "Imagem", "Imagens", "URL Imagens Externas"], ["imagem", "image", "foto"])
    marca_col = _first_existing(base, ["marca", "Marca", "brand"], ["marca", "brand"])
    categoria_col = _first_existing(base, ["categoria", "Categoria", "Categoria do produto"], ["categoria", "category"])

    codigo = _series(base, sku_col)
    gtin = _series(base, gtin_col)
    codigo = codigo.where(codigo.ne(""), gtin)

    nome = _series(base, nome_col)
    descricao = _series(base, desc_col)
    descricao = descricao.where(descricao.ne(""), nome)
    nome = nome.where(nome.ne(""), descricao)
    descricao_limpa = descricao.map(_clean_description)
    nome_limpo = nome.map(_clean_description)
    descricao_limpa = descricao_limpa.where(descricao_limpa.ne(""), nome_limpo)
    nome_limpo = nome_limpo.where(nome_limpo.ne(""), descricao_limpa)

    preco = _series(base, preco_col).map(_clean_price)
    if preco.eq("").any():
        preco_linha = base.apply(_price_from_row, axis=1)
        preco = preco.where(preco.ne(""), preco_linha)

    estoque = _series(base, estoque_col)
    estoque = estoque.map(lambda x: re.search(r"\d+", x).group(0) if re.search(r"\d+", x) else "")
    if estoque.eq("").any():
        estoque_linha = base.apply(_stock_from_row, axis=1)
        estoque = estoque.where(estoque.ne(""), estoque_linha)
    estoque = estoque.where(estoque.ne(""), "0")

    return {
        "base": base,
        "codigo": codigo,
        "descricao": descricao_limpa,
        "nome": nome_limpo,
        "preco": preco,
        "estoque": estoque,
        "gtin": gtin,
        "url": _series(base, url_col),
        "imagem": _series(base, imagem_col),
        "marca": _series(base, marca_col),
        "categoria": _series(base, categoria_col),
    }


def normalizar_captura_site_para_bling(df: pd.DataFrame, deposito_nome: str = "", tipo_operacao: str = "cadastro") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    fields = _extract_fields(df)
    operacao = _norm(tipo_operacao) or "cadastro"

    if operacao == "estoque":
        out = pd.DataFrame("", index=fields["base"].index, columns=BLING_ESTOQUE_COLUMNS)
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
        out = pd.DataFrame("", index=fields["base"].index, columns=BLING_CADASTRO_COLUMNS)
        out["Código"] = fields["codigo"]
        out["Descrição"] = fields["descricao"]
        out["Unidade"] = "PC"
        out["Origem"] = "1"
        out["Preço"] = fields["preco"]
        out["Situação"] = "Ativo"
        out["Estoque"] = fields["estoque"]
        out["Preço de custo"] = fields["preco"]
        out["Cód no fornecedor"] = fields["codigo"]
        out["Fornecedor"] = ""
        out["GTIN/EAN"] = fields["gtin"]
        out["GTIN/EAN da embalagem"] = fields["gtin"]
        out["Descrição do Produto no Fornecedor"] = fields["descricao"]
        out["Descrição Complementar"] = fields["descricao"]
        out["Descrição Curta"] = fields["descricao"]
        out["URL Imagens Externas"] = fields["imagem"]
        out["Link Externo"] = fields["url"]
        out["Condição do produto"] = "Novo"
        out["Unidade de medida"] = "PC"
        out["Preço de compra"] = fields["preco"]
        out["Marca"] = fields["marca"]
        out["Categoria do produto"] = fields["categoria"]

    out = out[out.apply(_is_valid_product, axis=1)].copy()
    if "Código" in out.columns and out["Código"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["Código"], keep="first")
    elif "Link Externo" in out.columns and out["Link Externo"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["Link Externo"], keep="first")
    elif "URL" in out.columns and out["URL"].astype(str).str.strip().ne("").any():
        out = out.drop_duplicates(subset=["URL"], keep="first")
    else:
        out = out.drop_duplicates(keep="first")

    return out.reset_index(drop=True).fillna("")
