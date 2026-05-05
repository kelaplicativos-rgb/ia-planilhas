from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd

from bling_app_zero.stable.site_price_extractor import extract_price_from_url


CADASTRO_SITE_COLUMNS = [
    "Código",
    "Descrição",
    "Descrição complementar",
    "Unidade",
    "NCM",
    "GTIN/EAN",
    "Preço unitário",
    "Preço de custo",
    "Marca",
    "Categoria",
    "URL imagens externas",
    "URL do produto",
]

_REMOVE_FROM_CADASTRO = {
    "estoque",
    "quantidade",
    "disponibilidade",
    "origem do estoque",
    "sku site",
    "balanco obrigatorio",
    "balanço obrigatório",
    "balanco",
    "balanço",
}

_GENERIC_NAMES = {
    "mega center eletrônicos",
    "mega center eletronicos",
    "mega center",
    "produto",
    "produtos",
    "loja",
}


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _find_col(df: pd.DataFrame, aliases: list[str]) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    normalized_aliases = [_norm(a) for a in aliases]
    columns = [str(c) for c in df.columns]
    for col in columns:
        nc = _norm(col)
        if nc in normalized_aliases:
            return col
    for col in columns:
        nc = _norm(col)
        if any(alias and (alias in nc or nc in alias) for alias in normalized_aliases):
            return col
    return ""


def _serie(df: pd.DataFrame, aliases: list[str], default: object = "") -> pd.Series:
    col = _find_col(df, aliases)
    if col and col in df.columns:
        return df[col].astype(str).fillna("")
    return pd.Series([default] * len(df), index=df.index)


def _url_from_row(value: object, fallback: object = "") -> str:
    raw = _clean(value)
    if raw:
        return raw
    return _clean(fallback)


def _name_from_url(url: object, fallback: object = "") -> str:
    raw = _clean(url)
    if raw:
        parsed = urlparse(raw)
        parts = [p for p in parsed.path.split("/") if p.strip()]
        if parts:
            slug = parts[-1]
            slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.I)
            slug = re.sub(r"^[0-9]+[-_ ]+", "", slug)
            slug = re.sub(r"[-_]+", " ", slug)
            slug = re.sub(r"\s+", " ", slug).strip()
            if slug:
                return slug.title()
    return _clean(fallback) or "Produto capturado do site"


def _code_from_url(url: object, index: int) -> str:
    raw = _clean(url)
    if raw:
        parsed = urlparse(raw)
        parts = [p for p in parsed.path.split("/") if p.strip()]
        candidate = parts[-1] if parts else parsed.netloc
        candidate = re.sub(r"[^A-Za-z0-9_-]+", "-", candidate).strip("-")
        if candidate:
            return candidate[:60]
    return f"SITE-{index:04d}"


def _is_generic_name(value: object) -> bool:
    text = _norm(value)
    if not text:
        return True
    return text in {_norm(x) for x in _GENERIC_NAMES} or text.endswith("mega center eletronicos")


def _fallback_price(urls: pd.Series, current: pd.Series) -> pd.Series:
    values: list[str] = []
    for url, price in zip(urls.astype(str).tolist(), current.astype(str).tolist()):
        price_clean = _clean(price)
        if price_clean and price_clean not in {"0", "0,00", "0.00"}:
            values.append(price_clean)
            continue
        captured = extract_price_from_url(url)
        values.append(captured if captured else price_clean)
    return pd.Series(values, index=current.index).fillna("")


def normalize_cadastro_site_dataframe(df: pd.DataFrame, raw_urls: str = "") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=CADASTRO_SITE_COLUMNS)

    out = pd.DataFrame(index=df.index)

    urls = _serie(df, ["URL do produto", "url produto", "url_produto", "url", "link", "link do produto"])
    if not urls.astype(str).str.strip().any():
        pasted = [u for u in re.split(r"[\n,;\s]+", str(raw_urls or "")) if u.strip()]
        if len(pasted) == len(df):
            urls = pd.Series(pasted, index=df.index)

    codigo = _serie(df, ["Código", "Codigo", "SKU", "sku", "referencia", "referência", "ref", "id"])
    codigo = pd.Series(
        [_clean(v) if _clean(v) else _code_from_url(urls.iloc[pos], pos + 1) for pos, v in enumerate(codigo.tolist())],
        index=df.index,
    )

    nome = _serie(df, ["Descrição", "Descricao", "Produto", "Nome", "Nome do produto", "Título", "Titulo", "title"])
    nome = pd.Series(
        [_name_from_url(urls.iloc[pos], fallback=codigo.iloc[pos]) if _is_generic_name(v) else _clean(v) for pos, v in enumerate(nome.tolist())],
        index=df.index,
    )

    descricao_complementar = _serie(
        df,
        [
            "Descrição complementar",
            "Descricao complementar",
            "Detalhes",
            "Descrição longa",
            "Descricao longa",
            "Complemento",
            "Informações",
            "Informacoes",
        ],
    )

    preco = _serie(df, ["Preço unitário", "Preco unitario", "Preço", "Preco", "Valor", "price", "Preço venda", "Preco venda"])
    preco = _fallback_price(urls, preco)

    imagens = _serie(df, ["URL imagens externas", "Imagens", "Imagem", "Fotos", "Foto", "image", "images"])
    imagens = imagens.astype(str).str.replace(",", "|", regex=False).str.replace(";", "|", regex=False)

    out["Código"] = codigo
    out["Descrição"] = nome
    out["Descrição complementar"] = descricao_complementar
    out["Unidade"] = _serie(df, ["Unidade", "UN", "UND"], default="UN")
    out["NCM"] = _serie(df, ["NCM"])
    out["GTIN/EAN"] = _serie(df, ["GTIN/EAN", "GTIN", "EAN", "Código de barras", "Codigo de barras", "Barcode"])
    out["Preço unitário"] = preco
    out["Preço de custo"] = _serie(df, ["Preço de custo", "Preco de custo", "Custo", "Valor custo"])
    out["Marca"] = _serie(df, ["Marca", "Brand", "Fabricante"])
    out["Categoria"] = _serie(df, ["Categoria", "Grupo", "Departamento", "Breadcrumb"])
    out["URL imagens externas"] = imagens
    out["URL do produto"] = urls

    for col in df.columns:
        if _norm(col) in _REMOVE_FROM_CADASTRO:
            continue
        if str(col) not in out.columns:
            out[str(col)] = df[col].astype(str).fillna("")

    return out.fillna("")
