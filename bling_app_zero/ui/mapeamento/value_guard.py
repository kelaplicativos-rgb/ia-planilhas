from __future__ import annotations

"""Blindagem contra mapeamento automático errado no preview/mapeamento.

Regra de produto:
    Se não for 1000% verdadeiro, não preencher automaticamente.

Este módulo corrige casos em que o mapeamento automático joga valores claramente
incompatíveis em colunas do modelo Bling, por exemplo:
- URL em Largura/Altura/Profundidade;
- descrição em campos fiscais;
- nome de produto em Preço de compra;
- GTIN em Código da lista de serviços;
- link em Tipo do item ou Condição do produto.

A limpeza é conservadora: quando o valor parece incompatível com o destino, fica
vazio para o usuário preencher manualmente.
"""

import re
import unicodedata
from typing import Callable

import pandas as pd


URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
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


def is_text_safe(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    return not is_url(text)


def is_url_or_images(value: object) -> bool:
    text = _value(value)
    if not text:
        return True
    # Campo de imagens pode receber múltiplas URLs separadas por |.
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if not parts:
        return True
    return all(is_url(part) for part in parts)


def is_unit(value: object) -> bool:
    text = normalize_name(value).upper()
    if not text:
        return True
    return text in {"UN", "UND", "UNIDADE", "PC", "PÇ", "PCA", "CX", "KG", "G", "LT", "ML", "M", "CM"}


def is_allowed_origin(value: object) -> bool:
    text = normalize_name(value)
    if not text:
        return True
    return text in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "nao informado", "nacional", "importado"}


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


# Destinos do modelo Bling que são perigosos: só devem receber valor automático
# se o valor passar numa validação de tipo bem objetiva.
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
    (("link externo", "video"), is_url),
    (("codigo", "cod no fornecedor", "codigo pai", "codigo integracao"), is_short_code),
]

# Colunas que nunca devem receber automaticamente nome/URL genéricos sem uma regra objetiva.
ALWAYS_CLEAR_WHEN_URL = {
    "tipo do item",
    "produto variacao",
    "classe de enquadramento do ipi",
    "grupo de tags tags",
    "grupo de produtos",
    "valor base icms st para retencao",
    "valor icms st para retencao",
    "valor icms proprio do substituto",
    "informacoes adicionais",
}

ALWAYS_CLEAR_WHEN_PRODUCT_TEXT = {
    "classe de enquadramento do ipi",
    "codigo da lista de servicos",
    "grupo de tags tags",
    "grupo de produtos",
    "preco de compra",
    "valor base icms st para retencao",
    "valor icms st para retencao",
    "valor icms proprio do substituto",
}


def _looks_like_product_text(value: object) -> bool:
    text = _value(value)
    if not text or is_url(text):
        return False
    # Produto costuma ter letras e espaços; campo fiscal/numérico não deveria receber isso.
    return bool(re.search(r"[A-Za-zÀ-ÿ]", text)) and len(text.split()) >= 2


def is_value_allowed_for_column(column_name: object, value: object) -> bool:
    text = _value(value)
    if not text:
        return True

    column = normalize_name(column_name)

    if column in ALWAYS_CLEAR_WHEN_URL and is_url(text):
        return False

    if column in ALWAYS_CLEAR_WHEN_PRODUCT_TEXT and _looks_like_product_text(text):
        return False

    for fragments, validator in COLUMN_VALIDATORS:
        if any(fragment in column for fragment in fragments):
            return validator(text)

    # Regra geral: URL só pode ficar em coluna claramente de URL/link/imagem/vídeo.
    if is_url(text) and not any(word in column for word in ("url", "link", "imagem", "video")):
        return False

    return True


def clean_invalid_preview_mappings(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa valores claramente incompatíveis com o nome da coluna.

    Retorna uma cópia do DataFrame. Não altera o objeto original.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    cleaned = df.copy()

    for column in cleaned.columns:
        mask_invalid = ~cleaned[column].map(lambda value: is_value_allowed_for_column(column, value))
        if mask_invalid.any():
            cleaned.loc[mask_invalid, column] = ""

    return cleaned
