from __future__ import annotations

"""Blindagem contra mapeamento automático errado no preview/mapeamento.

Regra de produto:
    Se não for 1000% verdadeiro, não preencher automaticamente.

Este módulo corrige casos em que o mapeamento automático joga valores claramente
incompatíveis em colunas do modelo Bling, por exemplo:
- URL em Largura/Altura/Profundidade/Condição/Tipo/ICMS;
- descrição em campos fiscais/grupos/preço de compra;
- GTIN em Código da lista de serviços;
- link em Tipo do item ou Condição do produto.

Também resgata o link real da página do produto quando ele apareceu em coluna
errada e coloca no campo correto (`Link Externo` e `URL do Produto`).
"""

import re
import unicodedata
from typing import Callable, Optional

import pandas as pd


URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
PRODUCT_PAGE_URL_RE = re.compile(r"https?://[^\s|,;\"]+/produto/[^\s|,;\"]+", re.IGNORECASE)
NUMERIC_RE = re.compile(r"^-?\d+(?:[\.,]\d+)?$")
INTEGER_RE = re.compile(r"^\d+$")
GTIN_RE = re.compile(r"^\d{8,14}$")
PRICE_RE = re.compile(r"^\d+(?:[\.,]\d{1,2})?$")


def normalize_name(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _value(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def is_url(value: object) -> bool:
    return bool(URL_RE.search(_value(value)))


def extract_product_page_url(value: object) -> str:
    text = _value(value)
    if not text:
        return ""
    match = PRODUCT_PAGE_URL_RE.search(text)
    return match.group(0).strip() if match else ""


def is_product_page_url(value: object) -> bool:
    return bool(extract_product_page_url(value))


def is_numeric(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    return bool(NUMERIC_RE.match(text))


def is_integer(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    return bool(INTEGER_RE.match(text))


def is_price(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    return bool(PRICE_RE.match(text))


def is_gtin(value: object) -> bool:
    text = re.sub(r"\D+", "", _value(value))
    if not text:
        return True
    return bool(GTIN_RE.match(text))


def is_short_code(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    if is_url(text):
        return False
    return len(text) <= 80


def is_unit(value: object) -> bool:
    text = normalize_name(value).upper()
    if not text:
        return True
    return text in {"UN", "UND", "UNIDADE", "PC", "PÇ", "PCA", "CX", "KG", "G", "LT", "ML", "M", "CM"}


def is_allowed_origin(value: object) -> bool:
    text = normalize_name(value)
    if not text:
        return True
    return text in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "nao informado", "nacional", "importado", "real", "nao informado"}


def is_allowed_condition(value: object) -> bool:
    text = normalize_name(value)
    if not text:
        return True
    return text in {"novo", "usado", "recondicionado"}


def is_bool_like(value: object) -> bool:
    text = normalize_name(value)
    if not text:
        return True
    return text in {"s", "n", "sim", "nao", "true", "false", "1", "0"}


def is_product_link_field(column_name: object) -> bool:
    column = normalize_name(column_name)
    return column in {
        "link externo",
        "url do produto",
        "link do produto",
        "pagina do produto",
        "url produto",
        "produto url",
    }


def is_image_field(column_name: object) -> bool:
    column = normalize_name(column_name)
    return "imagem" in column or "imagens" in column or "foto" in column or "fotos" in column


def is_url_or_images(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if not parts:
        return True
    return all(is_url(part) for part in parts)


COLUMN_VALIDATORS: list[tuple[tuple[str, ...], Callable[[object], bool]]] = [
    (("largura", "altura", "profundidade", "peso", "volumes", "itens p caixa"), is_numeric),
    (("preco", "valor ipi", "preco de custo", "preco de compra"), is_price),
    (("estoque", "estoque maximo", "estoque minimo", "cross docking", "meses garantia"), is_integer),
    (("gtin", "ean"), is_gtin),
    (("ncm", "cest", "codigo da lista de servicos"), is_integer),
    (("unidade", "unidade de medida"), is_unit),
    (("origem",), is_allowed_origin),
    (("condicao do produto",), is_allowed_condition),
    (("frete gratis", "clonar dados do pai"), is_bool_like),
    (("url imagens", "imagens externas"), is_url_or_images),
    (("link externo", "url do produto", "link do produto", "pagina do produto"), is_product_page_url),
    (("video",), is_url),
    (("codigo", "cod no fornecedor", "codigo pai", "codigo integracao"), is_short_code),
]

URL_FORBIDDEN_FRAGMENTS = (
    "largura",
    "altura",
    "profundidade",
    "peso",
    "tipo do item",
    "produto variacao",
    "condicao do produto",
    "clonar dados do pai",
    "frete gratis",
    "origem",
    "ncm",
    "cest",
    "classe de enquadramento",
    "codigo da lista de servicos",
    "grupo de tags",
    "grupo de produtos",
    "valor base icms",
    "valor icms st",
    "valor icms proprio",
    "preco de compra",
    "preco de custo",
    "informacoes adicionais",
)

PRODUCT_TEXT_FORBIDDEN_FRAGMENTS = (
    "classe de enquadramento",
    "codigo da lista de servicos",
    "grupo de tags",
    "grupo de produtos",
    "preco de compra",
    "preco de custo",
    "valor base icms",
    "valor icms st",
    "valor icms proprio",
    "ncm",
    "cest",
)


def _contains_any(column_norm: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in column_norm for fragment in fragments)


def _looks_like_product_text(value: object) -> bool:
    text = _value(value)
    if not text or is_url(text):
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", text)) and len(text.split()) >= 2


def is_value_allowed_for_column(column_name: object, value: object) -> bool:
    text = _value(value)
    if not text:
        return True

    column = normalize_name(column_name)

    if is_product_link_field(column_name):
        return is_product_page_url(text)

    if is_image_field(column_name):
        return is_url_or_images(text)

    # URL de produto só pode ficar em link/url/imagem/video. Nunca em dimensões,
    # fiscais, condição, grupos ou campos booleanos.
    if is_url(text):
        if _contains_any(column, URL_FORBIDDEN_FRAGMENTS):
            return False
        return any(word in column for word in ("url", "link", "imagem", "video", "foto"))

    if _looks_like_product_text(text) and _contains_any(column, PRODUCT_TEXT_FORBIDDEN_FRAGMENTS):
        return False

    for fragments, validator in COLUMN_VALIDATORS:
        if any(fragment in column for fragment in fragments):
            return validator(text)

    return True


def _find_product_link_columns(df: pd.DataFrame) -> list[str]:
    return [str(column) for column in df.columns if is_product_link_field(column)]


def _extract_row_product_url(row: pd.Series) -> str:
    for value in row.values:
        product_url = extract_product_page_url(value)
        if product_url:
            return product_url
    return ""


def repair_product_links(df: pd.DataFrame) -> pd.DataFrame:
    """Move/resgata o link da página do produto para `Link Externo`/`URL do Produto`."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    repaired = df.copy()
    link_columns = _find_product_link_columns(repaired)
    if not link_columns:
        return repaired

    for idx, row in repaired.iterrows():
        product_url = ""
        for link_column in link_columns:
            current = _value(row.get(link_column, ""))
            if current and is_product_page_url(current):
                product_url = current
                break
        if not product_url:
            product_url = _extract_row_product_url(row)
        if product_url:
            for link_column in link_columns:
                repaired.at[idx, link_column] = product_url

    return repaired


def clean_invalid_preview_mappings(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa valores claramente incompatíveis com o nome da coluna."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    cleaned = repair_product_links(df.copy())

    for column in cleaned.columns:
        mask_invalid = ~cleaned[column].map(lambda value: is_value_allowed_for_column(column, value))
        if mask_invalid.any():
            cleaned.loc[mask_invalid, column] = ""

    cleaned = repair_product_links(cleaned)
    return cleaned.fillna("")
