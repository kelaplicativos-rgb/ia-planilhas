from __future__ import annotations

"""Crawler página por página para produtos.

Regra principal:
    Listagem/categoria serve apenas para descobrir links.
    Os dados obrigatórios do produto devem ser extraídos entrando em cada
    página individual `/produto/...`.

Isto evita linhas preenchidas com dados genéricos da categoria ou mapeamentos
errados vindos de cards/listagens.
"""

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_TIMEOUT = 20
PRODUCT_PATH_RE = re.compile(r"/produto/[^\s\"'<>#?]+", re.IGNORECASE)
PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,\.]\d{2})")
GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")
SKU_RE = re.compile(r"(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[EÊ]NCIA)?)[\s:#\-]*([A-Z0-9._\-/]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ProductPageResult:
    url: str
    data: dict[str, str]


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    return response.text or ""


def normalize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, unescape(str(url or "")).strip())


def is_product_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return bool(parsed.scheme and parsed.netloc and PRODUCT_PATH_RE.search(parsed.path))


def discover_product_urls(seed_urls: Iterable[str], *, max_products: Optional[int] = None) -> list[str]:
    """Descobre URLs de produto a partir de páginas/listagens/URLs diretas."""
    discovered: list[str] = []
    seen: set[str] = set()

    for seed in seed_urls:
        seed = str(seed or "").strip()
        if not seed:
            continue

        if is_product_url(seed):
            if seed not in seen:
                seen.add(seed)
                discovered.append(seed)
            continue

        try:
            html = fetch_html(seed)
        except Exception:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            href = normalize_url(anchor.get("href", ""), seed)
            if not is_product_url(href):
                continue
            # remove query/hash para deduplicar página real
            parsed = urlparse(href)
            clean_url = parsed._replace(query="", fragment="").geturl()
            if clean_url in seen:
                continue
            seen.add(clean_url)
            discovered.append(clean_url)
            if max_products and len(discovered) >= max_products:
                return discovered

    return discovered


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                objects.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
            elif isinstance(item, list):
                stack.extend(item)
    return objects


def _first_meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return str(tag.get("content", "")).strip()
    return ""


def _clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_price(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    match = PRICE_RE.search(text)
    if not match:
        return ""
    price = match.group(1)
    if "," in price:
        return price.replace(".", "").replace(",", ".")
    return price


def _extract_from_json_ld(soup: BeautifulSoup) -> dict[str, str]:
    data: dict[str, str] = {}

    for obj in _json_ld_objects(soup):
        obj_type = obj.get("@type")
        types = obj_type if isinstance(obj_type, list) else [obj_type]
        types_norm = {str(t).lower() for t in types if t}
        if "product" not in types_norm:
            continue

        data["Descrição"] = data.get("Descrição") or _clean_text(obj.get("name"))
        data["Marca"] = data.get("Marca") or _clean_text(
            obj.get("brand", {}).get("name") if isinstance(obj.get("brand"), dict) else obj.get("brand")
        )
        data["Código"] = data.get("Código") or _clean_text(obj.get("sku") or obj.get("mpn"))
        data["Cód no fornecedor"] = data.get("Cód no fornecedor") or _clean_text(obj.get("sku") or obj.get("mpn"))
        data["GTIN/EAN"] = data.get("GTIN/EAN") or _clean_text(
            obj.get("gtin13") or obj.get("gtin14") or obj.get("gtin12") or obj.get("gtin8")
        )

        image = obj.get("image")
        if isinstance(image, list):
            data["URL Imagens Externas"] = data.get("URL Imagens Externas") or "|".join(str(i) for i in image if i)
        elif image:
            data["URL Imagens Externas"] = data.get("URL Imagens Externas") or str(image)

        offers = obj.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict):
            data["Preço"] = data.get("Preço") or _normalize_price(offers.get("price"))
            data["Preço unitário (OBRIGATÓRIO)"] = data.get("Preço unitário (OBRIGATÓRIO)") or data.get("Preço", "")

    return data


def _extract_images(soup: BeautifulSoup, page_url: str) -> str:
    images: list[str] = []
    seen: set[str] = set()

    candidates = []
    for tag in soup.select("img[src], img[data-src], img[data-original], source[srcset]"):
        for attr in ("src", "data-src", "data-original", "srcset"):
            value = tag.get(attr)
            if value:
                candidates.extend(str(value).split(","))

    for raw in candidates:
        url = raw.strip().split(" ")[0]
        if not url:
            continue
        abs_url = normalize_url(url, page_url)
        lower = abs_url.lower()
        if any(block in lower for block in ("logo", "sprite", "placeholder", "blank", "loading")):
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        images.append(abs_url)
        if len(images) >= 12:
            break

    return "|".join(images)


def extract_product_from_page(page_url: str, html: str) -> dict[str, str]:
    """Extrai dados somente da página individual do produto."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    data = _extract_from_json_ld(soup)

    title = data.get("Descrição") or _first_meta(soup, "og:title", "twitter:title")
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    data["Descrição"] = _clean_text(title)

    desc = _first_meta(soup, "description", "og:description", "twitter:description")
    if desc:
        data.setdefault("Descrição complementar", _clean_text(desc))

    price = data.get("Preço") or _normalize_price(
        _first_meta(soup, "product:price:amount", "og:price:amount") or text
    )
    data["Preço"] = price
    data["Preço unitário (OBRIGATÓRIO)"] = data.get("Preço unitário (OBRIGATÓRIO)") or price

    sku_match = SKU_RE.search(text)
    if sku_match:
        sku = _clean_text(sku_match.group(1))
        data["Código"] = data.get("Código") or sku
        data["Cód no fornecedor"] = data.get("Cód no fornecedor") or sku

    gtin = data.get("GTIN/EAN") or ""
    if not gtin:
        gtin_match = GTIN_RE.search(text)
        gtin = gtin_match.group(1) if gtin_match else ""
    data["GTIN/EAN"] = gtin

    images = data.get("URL Imagens Externas") or _first_meta(soup, "og:image", "twitter:image") or _extract_images(soup, page_url)
    data["URL Imagens Externas"] = images

    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag and canonical_tag.get("href"):
        canonical = normalize_url(canonical_tag.get("href"), page_url)

    data["Link Externo"] = canonical if is_product_url(canonical) else page_url
    data["URL do Produto"] = data["Link Externo"]
    data["Fonte captura"] = "pagina_produto"

    # Não forçar estoque: o usuário pediu para tirar apenas o estoque da obrigatoriedade.
    data.pop("Estoque", None)

    return {key: _clean_text(value) for key, value in data.items() if _clean_text(value)}


def crawl_product_pages(seed_urls: Iterable[str], *, max_products: Optional[int] = None) -> list[dict[str, str]]:
    """Descobre e visita cada página de produto, retornando uma linha por página."""
    product_urls = discover_product_urls(seed_urls, max_products=max_products)
    rows: list[dict[str, str]] = []

    for product_url in product_urls:
        try:
            html = fetch_html(product_url)
            row = extract_product_from_page(product_url, html)
        except Exception as exc:
            row = {
                "Link Externo": product_url,
                "URL do Produto": product_url,
                "Fonte captura": "pagina_produto_erro",
                "Erro captura": str(exc),
            }
        rows.append(row)

    return rows


def crawl_product_pages_dataframe(seed_urls: Iterable[str], *, max_products: Optional[int] = None) -> pd.DataFrame:
    return pd.DataFrame(crawl_product_pages(seed_urls, max_products=max_products))
