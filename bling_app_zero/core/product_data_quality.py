from __future__ import annotations

"""Qualidade dos dados capturados por página de produto.

Objetivo:
- Não mascarar dado ausente com valores falsos, como preço `0,00`.
- Enriquecer marca quando ela aparece claramente no título/nome do produto.
- Nunca manter nome da loja/fornecedor como marca do produto.
- Harmonizar aliases importantes como `Link Externo` e `URL do Produto`.
- Preservar campos opcionais quando vierem de verdade, como NCM, CEST e preço de custo.
- Limpar/deduplicar imagens externas sem inventar dados.
"""

import re
from typing import Iterable

import pandas as pd

from bling_app_zero.core.brand_from_title import infer_brand_from_title


ZERO_LIKE = {"0", "0,0", "0,00", "0.0", "0.00", "r$ 0,00", "r$0,00"}
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
STORE_BRAND_VALUES = {
    "mega center eletronicos",
    "mega center eletrônicos",
    "megacenter eletronicos",
    "megacenter eletrônicos",
    "kel aplicativos",
    "stoqui",
}
TRACKING_IMAGE_FRAGMENTS = (
    "facebook.com/tr",
    "facebook.com",
    "pixel",
    "analytics",
    "google-analytics",
    "gtag",
    "doubleclick",
    "tracking",
    "track",
    "noscript",
)

PRICE_COLUMNS = {
    "Preço",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de custo",
    "Preço de compra",
}

OPTIONAL_EMPTY_COLUMNS = {
    "NCM",
    "CEST",
    "Preço de custo",
    "Preço de compra",
    "Categoria do produto",
    "Departamento",
    "Descrição Complementar",
    "Descrição complementar",
}

PRODUCT_URL_ALIASES = (
    "URL do Produto",
    "Link Externo",
    "Url Produto",
    "URL Produto",
    "Link do Produto",
    "Página do Produto",
    "Pagina do Produto",
)

DESCRIPTION_COMPLEMENT_ALIASES = (
    "Descrição complementar",
    "Descrição Complementar",
    "Descricao complementar",
    "Descricao Complementar",
    "Complemento",
    "Descrição detalhada",
    "Descricao detalhada",
)

CATEGORY_ALIASES = (
    "Categoria",
    "Categoria do produto",
    "Categoria Produto",
    "Departamento",
)

IMAGE_ALIASES = (
    "URL Imagens Externas",
    "Imagens Externas",
    "Imagens",
    "Imagem",
    "Fotos",
    "Foto",
)

TITLE_ALIASES = (
    "Descrição",
    "Descricao",
    "Nome",
    "Produto",
    "Título",
    "Titulo",
    "Title",
)

PREFERRED_ORDER = [
    "Código",
    "Cód no fornecedor",
    "Descrição",
    "Descrição complementar",
    "Unidade",
    "GTIN/EAN",
    "GTIN/EAN da embalagem",
    "Preço",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de custo",
    "Preço de compra",
    "Marca",
    "Categoria",
    "Categoria do produto",
    "Departamento",
    "NCM",
    "CEST",
    "URL Imagens Externas",
    "Link Externo",
    "URL do Produto",
    "Fonte captura",
    "Erro captura",
]


def _text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _norm(value: object) -> str:
    text = _text(value).lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _first_value(row: dict[str, str], aliases: Iterable[str]) -> str:
    for key in aliases:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _is_zero_like(value: object) -> bool:
    return _text(value).lower().strip() in ZERO_LIKE


def _is_url(value: object) -> bool:
    return bool(URL_RE.search(_text(value)))


def _is_tracking_image(url: str) -> bool:
    low = str(url or "").lower()
    return any(fragment in low for fragment in TRACKING_IMAGE_FRAGMENTS)


def _normalize_pipe_urls(value: object, *, max_items: int = 20) -> str:
    text = _text(value)
    if not text:
        return ""

    raw_parts = re.split(r"[|,\n\r\t]+", text)
    result: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        url = part.strip().strip('"\'')
        if not url or not _is_url(url):
            continue
        lower = url.lower()
        if any(block in lower for block in ("logo", "sprite", "placeholder", "blank", "loading", "favicon")):
            continue
        if _is_tracking_image(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= max_items:
            break
    return "|".join(result)


def _harmonize_product_url(cleaned: dict[str, str]) -> None:
    url = _first_value(cleaned, PRODUCT_URL_ALIASES)
    if not url:
        return
    cleaned["URL do Produto"] = url
    cleaned["Link Externo"] = url


def _harmonize_description_complement(cleaned: dict[str, str]) -> None:
    desc = _first_value(cleaned, DESCRIPTION_COMPLEMENT_ALIASES)
    if not desc:
        return
    if desc == cleaned.get("Descrição"):
        return
    cleaned["Descrição complementar"] = desc


def _harmonize_category(cleaned: dict[str, str]) -> None:
    category = _first_value(cleaned, CATEGORY_ALIASES)
    if category:
        cleaned["Categoria"] = category


def _harmonize_images(cleaned: dict[str, str]) -> None:
    images = []
    for alias in IMAGE_ALIASES:
        value = _normalize_pipe_urls(cleaned.get(alias))
        if value:
            images.append(value)
    final = _normalize_pipe_urls("|".join(images))
    if final:
        cleaned["URL Imagens Externas"] = final
    elif "URL Imagens Externas" in cleaned:
        cleaned.pop("URL Imagens Externas", None)


def _is_store_brand(value: object) -> bool:
    return _norm(value) in STORE_BRAND_VALUES


def _harmonize_brand_from_title(cleaned: dict[str, str]) -> None:
    title = _first_value(cleaned, TITLE_ALIASES)
    title_brand = infer_brand_from_title(title)

    current_brand = cleaned.get("Marca", "")
    if current_brand and not _is_store_brand(current_brand):
        return

    if title_brand:
        cleaned["Marca"] = title_brand
    elif _is_store_brand(current_brand):
        cleaned.pop("Marca", None)


def normalize_product_row(row: dict[str, object]) -> dict[str, str]:
    cleaned: dict[str, str] = {str(k).strip(): _text(v) for k, v in row.items() if _text(v)}

    _harmonize_product_url(cleaned)
    _harmonize_description_complement(cleaned)
    _harmonize_category(cleaned)
    _harmonize_images(cleaned)
    _harmonize_brand_from_title(cleaned)

    for col in PRICE_COLUMNS:
        if _is_zero_like(cleaned.get(col)):
            cleaned.pop(col, None)

    if cleaned.get("GTIN/EAN") and not cleaned.get("GTIN/EAN da embalagem"):
        cleaned["GTIN/EAN da embalagem"] = cleaned["GTIN/EAN"]

    for col in OPTIONAL_EMPTY_COLUMNS:
        if not cleaned.get(col):
            cleaned.pop(col, None)

    for alias in PRODUCT_URL_ALIASES:
        if alias not in {"URL do Produto", "Link Externo"}:
            cleaned.pop(alias, None)
    for alias in DESCRIPTION_COMPLEMENT_ALIASES:
        if alias != "Descrição complementar":
            cleaned.pop(alias, None)
    for alias in IMAGE_ALIASES:
        if alias != "URL Imagens Externas":
            cleaned.pop(alias, None)

    return cleaned


def normalize_product_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    return [normalize_product_row(row) for row in rows]


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    ordered = [col for col in PREFERRED_ORDER if col in df.columns]
    remaining = [col for col in df.columns if col not in ordered]
    return df[ordered + remaining]


def normalize_product_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    normalized = pd.DataFrame(normalize_product_rows(df.to_dict(orient="records")))
    if normalized.empty:
        return normalized
    return _order_columns(normalized)
