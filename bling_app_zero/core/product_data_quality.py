from __future__ import annotations

"""Qualidade dos dados capturados por página de produto."""

import ast
import re
from typing import Iterable

import pandas as pd

from bling_app_zero.core.brand_from_title import infer_brand_from_title

ZERO_LIKE = {"0", "0,0", "0,00", "0.0", "0.00", "r$ 0,00", "r$0,00"}
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
EXTRACT_URL_RE = re.compile(r"(?:https?://|www\.)[^\s\"'<>]+", re.IGNORECASE)
STORE_BRAND_VALUES = {"mega center eletronicos", "mega center eletrônicos", "megacenter eletronicos", "megacenter eletrônicos", "kel aplicativos", "stoqui"}
TRACKING_IMAGE_FRAGMENTS = ("facebook.com/tr", "facebook.com", "pixel", "analytics", "google-analytics", "gtag", "doubleclick", "tracking", "track", "noscript")
DESC_BAD = (
    "mega center eletronicos", "mega center eletrônicos", "todos os direitos reservados", "redes sociais", "facebook", "instagram", "whatsapp",
    "conecte se conosco", "conecte-se conosco", "atendimento", "formas de pagamento", "política de privacidade", "politica de privacidade",
    "trocas e devoluções", "trocas e devolucoes", "newsletter", "cadastre seu email", "departamentos", "categorias", "menu", "minha conta",
    "login", "carrinho", "comprar", "adicionar ao carrinho", "quem somos", "sobre nós", "sobre nos",
)

PRICE_COLUMNS = {"Preço", "Preço unitário", "Preço unitário (OBRIGATÓRIO)", "Preço de custo", "Preço de compra"}
PRODUCT_URL_ALIASES = ("URL do Produto", "Link Externo", "Url Produto", "URL Produto", "Link do Produto", "Página do Produto", "Pagina do Produto")
DESCRIPTION_COMPLEMENT_ALIASES = ("Descrição complementar", "Descrição Complementar", "Descricao complementar", "Descricao Complementar", "Descrição Curta", "Descrição curta", "Descricao curta", "Complemento", "Descrição detalhada", "Descricao detalhada")
CATEGORY_ALIASES = ("Categoria", "Categoria do produto", "Categoria Produto", "Departamento")
IMAGE_ALIASES = (
    "URL Imagens Externas",
    "URL imagens externas",
    "Imagens Externas",
    "Imagens",
    "Imagem",
    "Fotos",
    "Foto",
    "image_urls",
    "image urls",
    "image_url",
    "image url",
    "images",
    "image",
    "imgs",
    "img",
    "main_image",
    "main image",
    "thumbnail",
    "thumbnails",
    "gallery",
    "galeria",
    "url_imagem",
    "url imagens",
    "url_imagens",
    "imagem principal",
    "foto principal",
)
TITLE_ALIASES = ("Descrição", "Descricao", "Nome", "Produto", "Título", "Titulo", "Title")

BLING_CADASTRO_COLUMNS = [
    "ID", "Código", "Descrição", "Unidade", "NCM", "Origem", "Preço", "Valor IPI fixo", "Observações", "Situação", "Estoque", "Preço de custo", "Cód no fornecedor", "Fornecedor", "Localização", "Estoque maximo", "Estoque minimo", "Peso líquido (Kg)", "Peso bruto (Kg)", "GTIN/EAN", "GTIN/EAN da embalagem", "Largura do Produto", "Altura do Produto", "Profundidade do produto", "Data Validade", "Descrição do Produto no Fornecedor", "Descrição Complementar", "Itens p/ caixa", "Produto Variação", "Tipo Produção", "Classe de enquadramento do IPI", "Código da lista de serviços", "Tipo do item", "Grupo de Tags/Tags", "Tributos", "Código Pai", "Código Integração", "Grupo de produtos", "Marca", "CEST", "Volumes", "Descrição Curta", "Cross-Docking", "URL Imagens Externas", "Link Externo", "Meses Garantia no Fornecedor", "Clonar dados do pai", "Condição do produto", "Frete Grátis", "Número FCI", "Vídeo", "Departamento", "Unidade de medida", "Preço de compra", "Valor base ICMS ST para retenção", "Valor ICMS ST para retenção", "Valor ICMS próprio do substituto", "Categoria do produto", "Informações Adicionais",
]

DEFAULTS_BY_COLUMN_NAME = {
    "unidade": "UN",
    "unidade de medida": "UN",
    "situacao": "Ativo",
    "origem": "0",
    "itens p caixa": "1",
    "itens por caixa": "1",
    "tipo do item": "Produto",
    "volumes": "1",
    "condicao do produto": "Novo",
    "frete gratis": "Não",
}

PREFERRED_ORDER = [col for col in BLING_CADASTRO_COLUMNS]


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(_text(item) for item in value if _text(item))
    if pd.isna(value):
        return ""
    return str(value).strip()


def _norm(value: object) -> str:
    text = _text(value).lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _first_value(row: dict[str, str], aliases: Iterable[str]) -> str:
    aliases_norm = {_norm(alias) for alias in aliases}
    for key in aliases:
        value = _text(row.get(key))
        if value:
            return value
    for key, value in row.items():
        if _norm(key) in aliases_norm and _text(value):
            return _text(value)
    return ""


def _is_zero_like(value: object) -> bool:
    return _text(value).lower().strip() in ZERO_LIKE


def _is_url(value: object) -> bool:
    return bool(URL_RE.search(_text(value)))


def _is_tracking_image(url: str) -> bool:
    low = str(url or "").lower()
    return any(fragment in low for fragment in TRACKING_IMAGE_FRAGMENTS)


def _candidate_parts_from_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_candidate_parts_from_value(item))
        return parts

    text = _text(value)
    if not text:
        return []

    stripped = text.strip()
    if stripped.startswith(("[", "{")) and stripped.endswith(("]", "}")):
        try:
            parsed = ast.literal_eval(stripped)
            if parsed is not value:
                parsed_parts = _candidate_parts_from_value(parsed)
                if parsed_parts:
                    return parsed_parts
        except Exception:
            pass

    found = EXTRACT_URL_RE.findall(text)
    if found:
        return found

    return re.split(r"[|,\n\r\t]+", text)


def _clean_url_candidate(value: object) -> str:
    url = _text(value).strip().strip('"\'[]{}()')
    url = re.sub(r"[\]\[\}\{\)\(\"']+$", "", url).strip()
    url = re.sub(r"[.,;:]+$", "", url).strip()
    if url.startswith("www."):
        url = "https://" + url
    return url


def _normalize_pipe_urls(value: object, *, max_items: int = 20) -> str:
    parts = _candidate_parts_from_value(value)
    if not parts:
        return ""

    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        url = _clean_url_candidate(part)
        if not url or not _is_url(url):
            continue
        lower = url.lower()
        if any(block in lower for block in ("logo", "sprite", "placeholder", "blank", "loading", "favicon")) or _is_tracking_image(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= max_items:
            break
    return "|".join(result)


def _clean_description(value: object, title: str = "") -> str:
    text = _text(value).replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    bad_norm = [_norm(x) for x in DESC_BAD]
    title_norm = _norm(title)
    cleaned: list[str] = []
    seen: set[str] = set()
    for piece in re.split(r"(?<=\.)\s+|\s{2,}|\|", text):
        part = _text(piece).strip(" -•|:;")
        norm = _norm(part)
        if not part or len(part) < 18:
            continue
        if title_norm and norm == title_norm:
            continue
        if any(bad in norm for bad in bad_norm):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append(part)
        if len(" ".join(cleaned)) >= 1800:
            break
    return " ".join(cleaned).strip()[:2000]


def _harmonize_product_url(cleaned: dict[str, str]) -> None:
    url = _first_value(cleaned, PRODUCT_URL_ALIASES)
    if url:
        cleaned["URL do Produto"] = url
        cleaned["Link Externo"] = url


def _harmonize_description(cleaned: dict[str, str]) -> None:
    title = _first_value(cleaned, TITLE_ALIASES)
    desc = _clean_description(_first_value(cleaned, DESCRIPTION_COMPLEMENT_ALIASES), title=title)
    if desc:
        cleaned["Descrição Complementar"] = desc
        cleaned["Descrição complementar"] = desc
        cleaned["Descrição Curta"] = desc
    else:
        cleaned.pop("Descrição Complementar", None)
        cleaned.pop("Descrição complementar", None)
        cleaned.pop("Descrição Curta", None)


def _harmonize_category(cleaned: dict[str, str]) -> None:
    category = _first_value(cleaned, CATEGORY_ALIASES)
    if category:
        cleaned["Categoria"] = category
        cleaned["Categoria do produto"] = category
        cleaned["Departamento"] = cleaned.get("Departamento") or category


def _column_looks_like_image_source(column_name: object) -> bool:
    norm = _norm(column_name)
    tokens = {"imagem", "imagens", "image", "images", "img", "foto", "fotos", "gallery", "galeria", "thumbnail"}
    return any(token in norm.split() or token in norm for token in tokens)


def _harmonize_images(cleaned: dict[str, str]) -> None:
    images: list[str] = []

    for alias in IMAGE_ALIASES:
        value = _normalize_pipe_urls(_first_value(cleaned, [alias]))
        if value:
            images.append(value)

    for key, value in list(cleaned.items()):
        if _column_looks_like_image_source(key):
            normalized = _normalize_pipe_urls(value)
            if normalized:
                images.append(normalized)

    final = _normalize_pipe_urls("|".join(images))
    if final:
        cleaned["URL Imagens Externas"] = final
        cleaned["URL imagens externas"] = final
        cleaned["Imagens"] = final
    else:
        cleaned.pop("URL Imagens Externas", None)
        cleaned.pop("URL imagens externas", None)


def _is_store_brand(value: object) -> bool:
    return _norm(value) in {_norm(x) for x in STORE_BRAND_VALUES}


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


def _apply_defaults(cleaned: dict[str, str]) -> None:
    cleaned.setdefault("Unidade", "UN")
    cleaned.setdefault("Unidade de medida", "UN")
    cleaned.setdefault("Origem", "0")
    cleaned.setdefault("Situação", "Ativo")
    cleaned.setdefault("Itens p/ caixa", "1")
    cleaned.setdefault("Tipo do item", "Produto")
    cleaned.setdefault("Volumes", "1")
    cleaned.setdefault("Condição do produto", "Novo")
    cleaned.setdefault("Frete Grátis", "Não")

    for key in list(cleaned.keys()):
        norm_key = _norm(key)
        if not cleaned.get(key) and norm_key in DEFAULTS_BY_COLUMN_NAME:
            cleaned[key] = DEFAULTS_BY_COLUMN_NAME[norm_key]


def normalize_product_row(row: dict[str, object]) -> dict[str, str]:
    cleaned: dict[str, str] = {str(k).strip(): _text(v) for k, v in row.items() if _text(v)}

    _harmonize_product_url(cleaned)
    _harmonize_description(cleaned)
    _harmonize_category(cleaned)
    _harmonize_images(cleaned)
    _harmonize_brand_from_title(cleaned)

    for col in PRICE_COLUMNS:
        if _is_zero_like(cleaned.get(col)):
            cleaned.pop(col, None)

    if cleaned.get("Preço"):
        cleaned.setdefault("Preço unitário", cleaned["Preço"])
        cleaned.setdefault("Preço unitário (OBRIGATÓRIO)", cleaned["Preço"])
    if cleaned.get("Preço de custo") and not cleaned.get("Preço de compra"):
        cleaned["Preço de compra"] = cleaned["Preço de custo"]

    if cleaned.get("GTIN/EAN") and not cleaned.get("GTIN/EAN da embalagem"):
        cleaned["GTIN/EAN da embalagem"] = cleaned["GTIN/EAN"]

    _apply_defaults(cleaned)

    for alias in PRODUCT_URL_ALIASES:
        if alias not in {"URL do Produto", "Link Externo"}:
            cleaned.pop(alias, None)
    for alias in DESCRIPTION_COMPLEMENT_ALIASES:
        if alias not in {"Descrição Complementar", "Descrição complementar", "Descrição Curta"}:
            cleaned.pop(alias, None)
    for alias in IMAGE_ALIASES:
        if alias not in {"URL Imagens Externas", "URL imagens externas", "Imagens"}:
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
