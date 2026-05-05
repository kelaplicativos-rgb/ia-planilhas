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

Também resgata o link real da página do produto quando ele apareceu em coluna
errada e coloca no campo correto (`Link Externo`), porque cada produto precisa
manter o próprio link de origem página por página.
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
    return text in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "nao informado", "nacional", "importado", "real"}


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
    (("link externo", "url do produto", "link do produto", "pagina do produto"), is_product_page_url),
    (("video",), is_url),
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

    if is_product_link_field(column_name):
        return is_product_page_url(text)

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


def _find_product_link_column(df: pd.DataFrame) -> Optional[str]:
    for column in df.columns:
        if is_product_link_field(column):
            return str(column)
    return None


def _extract_row_product_url(row: pd.Series) -> str:
    for value in row.values:
        product_url = extract_product_page_url(value)
        if product_url:
            return product_url
    return ""


def repair_product_links(df: pd.DataFrame) -> pd.DataFrame:
    """Move/resgata o link da página do produto para `Link Externo`.

    Se a coluna `Link Externo` existir e estiver vazia, procura em qualquer campo
    da linha por uma URL `/produto/...` e preenche corretamente. Não cria coluna
    nova para não alterar o modelo do Bling.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    repaired = df.copy()
    link_column = _find_product_link_column(repaired)
    if not link_column:
        return repaired

    for idx, row in repaired.iterrows():
        current = _value(row.get(link_column, ""))
        if current and is_product_page_url(current):
            continue

        product_url = _extract_row_product_url(row)
        if product_url:
            repaired.at[idx, link_column] = product_url

    return repaired


def clean_invalid_preview_mappings(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa valores claramente incompatíveis com o nome da coluna.

    Retorna uma cópia do DataFrame. Não altera o objeto original.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    cleaned = repair_product_links(df.copy())

    for column in cleaned.columns:
        mask_invalid = ~cleaned[column].map(lambda value: is_value_allowed_for_column(column, value))
        if mask_invalid.any():
            cleaned.loc[mask_invalid, column] = ""

    # Segunda passada: se alguma limpeza apagou o link correto, tenta resgatar de novo.
    cleaned = repair_product_links(cleaned)
    return cleaned
