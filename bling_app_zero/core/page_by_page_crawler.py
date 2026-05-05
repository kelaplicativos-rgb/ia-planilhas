from __future__ import annotations

"""Crawler página por página para produtos.

Regra principal:
    1. A varredura normal/listagem é sempre a fonte primária para descobrir URLs.
    2. O sistema entra em cada página individual `/produto/...` para extrair dados.
    3. Sitemap entra por último, apenas para complementar URLs de produto que a
       varredura inicial não detectou.

Campos opcionais como NCM, preço de custo, categoria etc. podem vir SIM, desde
que encontrados de verdade na página/dados estruturados. O crawler não inventa
nem força coluna sem dado real.
"""

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.site_sitemap import discover_product_urls_from_sitemaps


DEFAULT_TIMEOUT = 20
PRODUCT_PATH_RE = re.compile(r"/produto/[^\s\"'<>#?]+", re.IGNORECASE)
PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,\.]\d{2})")
GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")
SKU_RE = re.compile(r"(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[EÊ]NCIA)?)[\s:#\-]*([A-Z0-9._\-/]+)", re.IGNORECASE)
NCM_RE = re.compile(r"\bNCM\b[\s:#\-]*([0-9.]{6,12})", re.IGNORECASE)
CEST_RE = re.compile(r"\bCEST\b[\s:#\-]*([0-9.]{5,12})", re.IGNORECASE)
COST_RE = re.compile(r"(?:pre[cç]o\s+de\s+custo|custo)\s*[:\-]?\s*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,\.]\d{2})", re.IGNORECASE)

DESCRIPTION_SELECTORS = (
    "#descricao",
    "#description",
    ".descricao",
    ".description",
    ".product-description",
    ".produto-descricao",
    ".product-details",
    ".product-detail",
    ".product-tabs",
    ".tab-content",
    "[class*='descricao']",
    "[class*='description']",
    "[class*='especifica']",
    "[class*='detalhe']",
)

PRICE_SELECTORS = (
    "[itemprop='price']",
    "[data-price]",
    "[data-preco]",
    "[class*='price']",
    "[class*='preco']",
    "[class*='valor']",
    ".product-price",
    ".produto-preco",
)

DESCRIPTION_BLOCKLIST = (
    "mega center eletronicos",
    "mega center eletrônicos",
    "todos os direitos reservados",
    "redes sociais",
    "facebook",
    "instagram",
    "whatsapp",
    "conecte se conosco",
    "conecte-se conosco",
    "atendimento",
    "formas de pagamento",
    "política de privacidade",
    "politica de privacidade",
    "trocas e devoluções",
    "trocas e devolucoes",
    "newsletter",
    "cadastre seu email",
    "departamentos",
    "categorias",
    "menu",
    "minha conta",
    "login",
    "carrinho",
    "comprar",
    "adicionar ao carrinho",
)


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


def _allowed_hosts(seed_urls: list[str]) -> set[str]:
    hosts: set[str] = set()
    for seed in seed_urls:
        parsed = urlparse(seed)
        if parsed.netloc:
            hosts.add(parsed.netloc.lower())
    return hosts


def _same_seed_host(url: str, hosts: set[str]) -> bool:
    if not hosts:
        return True
    host = urlparse(url).netloc.lower()
    return host in hosts


def discover_product_urls(
    seed_urls: Iterable[str],
    *,
    max_products: Optional[int] = None,
    use_sitemap: bool = True,
) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()
    seeds = [str(seed or "").strip() for seed in seed_urls if str(seed or "").strip()]
    seed_hosts = _allowed_hosts(seeds)

    def add_url(url: str) -> bool:
        if not is_product_url(url):
            return False
        parsed = urlparse(url)
        clean_url = parsed._replace(query="", fragment="").geturl()
        if not _same_seed_host(clean_url, seed_hosts):
            return False
        if clean_url in seen:
            return False
        seen.add(clean_url)
        discovered.append(clean_url)
        return bool(max_products and len(discovered) >= max_products)

    for seed in seeds:
        if add_url(seed):
            return discovered
        if is_product_url(seed):
            continue

        try:
            html = fetch_html(seed)
        except Exception:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            href = normalize_url(anchor.get("href", ""), seed)
            if add_url(href):
                return discovered

    if use_sitemap and (not max_products or len(discovered) < max_products):
        remaining = None if max_products is None else max_products - len(discovered)
        for sitemap_url in discover_product_urls_from_sitemaps(seeds, max_products=remaining or 5000):
            if add_url(sitemap_url):
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
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_price(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    matches = PRICE_RE.findall(text)
    if not matches:
        return ""
    candidates: list[float] = []
    original: dict[float, str] = {}
    for match in matches:
        raw = str(match)
        value_txt = raw.replace(".", "").replace(",", ".") if "," in raw else raw
        try:
            number = float(value_txt)
        except Exception:
            continue
        if number <= 0:
            continue
        candidates.append(number)
        original[number] = value_txt
    if not candidates:
        return ""
    chosen = max(candidates)
    return f"{chosen:.2f}"


def _extract_category(soup: BeautifulSoup) -> str:
    crumbs: list[str] = []
    for selector in (
        ".breadcrumb a",
        "nav.breadcrumb a",
        "[itemtype*='BreadcrumbList'] [itemprop='name']",
        "[class*='breadcrumb'] a",
    ):
        for node in soup.select(selector):
            text = _clean_text(node.get_text(" ", strip=True))
            if text and text.lower() not in {"home", "início", "inicio"} and text not in crumbs:
                crumbs.append(text)
        if crumbs:
            break
    return " > ".join(crumbs)


def _description_is_noise(text: str) -> bool:
    low = _clean_text(text).lower()
    if not low or len(low) < 20:
        return True
    if any(block in low for block in DESCRIPTION_BLOCKLIST):
        return True
    return False


def _clean_description_block(text: str, title: str = "") -> str:
    text = _clean_text(text)
    if not text:
        return ""
    pieces = re.split(r"(?:\s{2,}|(?<=\.)\s+|\|)", text)
    cleaned: list[str] = []
    seen: set[str] = set()
    title_clean = _clean_text(title).lower()
    for piece in pieces:
        part = _clean_text(piece).strip(" -•|:;")
        if not part:
            continue
        low = part.lower()
        if title_clean and low == title_clean:
            continue
        if _description_is_noise(part):
            continue
        if low in seen:
            continue
        seen.add(low)
        cleaned.append(part)
        if len(" ".join(cleaned)) >= 1200:
            break
    result = " ".join(cleaned).strip()
    return result[:2000]


def _extract_description_from_page(soup: BeautifulSoup, title: str = "") -> str:
    candidates: list[str] = []
    for selector in DESCRIPTION_SELECTORS:
        for node in soup.select(selector):
            # remove áreas que normalmente são propaganda/rodapé/navegação dentro do bloco
            for bad in node.select("script, style, nav, footer, header, form, button, .social, .newsletter, .menu, .breadcrumb"):
                bad.decompose()
            text = _clean_description_block(node.get_text(" ", strip=True), title=title)
            if text:
                candidates.append(text)
    if candidates:
        return max(candidates, key=len)
    return ""


def _extract_price_from_page(soup: BeautifulSoup, full_text: str) -> str:
    for meta_names in (
        ("product:price:amount", "og:price:amount", "price", "twitter:data1"),
    ):
        price = _normalize_price(_first_meta(soup, *meta_names))
        if price:
            return price

    candidates: list[str] = []
    for selector in PRICE_SELECTORS:
        for node in soup.select(selector):
            attr_price = node.get("data-price") or node.get("data-preco") or node.get("content")
            if attr_price:
                candidates.append(str(attr_price))
            txt = node.get_text(" ", strip=True)
            if txt:
                candidates.append(txt)

    for candidate in candidates:
        price = _normalize_price(candidate)
        if price:
            return price

    return _normalize_price(full_text)


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
        data["Categoria"] = data.get("Categoria") or _clean_text(obj.get("category"))

        for key, target in (("ncm", "NCM"), ("cest", "CEST"), ("cost", "Preço de custo"), ("costPrice", "Preço de custo")):
            if obj.get(key):
                data[target] = data.get(target) or _clean_text(obj.get(key))

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
    for meta in soup.select("meta[property='og:image'], meta[name='twitter:image']"):
        if meta.get("content"):
            candidates.append(str(meta.get("content")))

    for tag in soup.select("img[src], img[data-src], img[data-original], img[data-zoom-image], source[srcset]"):
        for attr in ("src", "data-src", "data-original", "data-zoom-image", "srcset"):
            value = tag.get(attr)
            if value:
                candidates.extend(str(value).split(","))

    for raw in candidates:
        url = raw.strip().split(" ")[0]
        if not url:
            continue
        abs_url = normalize_url(url, page_url)
        lower = abs_url.lower()
        if any(block in lower for block in ("logo", "sprite", "placeholder", "blank", "loading", "favicon", "facebook.com/tr")):
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        images.append(abs_url)
        if len(images) >= 20:
            break

    return "|".join(images)


def _extract_regex_optional(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    ncm = NCM_RE.search(text)
    cest = CEST_RE.search(text)
    cost = COST_RE.search(text)
    if ncm:
        data["NCM"] = re.sub(r"\D+", "", ncm.group(1))
    if cest:
        data["CEST"] = re.sub(r"\D+", "", cest.group(1))
    if cost:
        data["Preço de custo"] = _normalize_price(cost.group(1))
    return {k: v for k, v in data.items() if v}


def extract_product_from_page(page_url: str, html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    data = _extract_from_json_ld(soup)

    title = data.get("Descrição") or _first_meta(soup, "og:title", "twitter:title")
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    data["Descrição"] = _clean_text(title)

    desc = _extract_description_from_page(soup, title=data.get("Descrição", ""))
    if not desc:
        desc = _clean_description_block(_first_meta(soup, "description", "og:description", "twitter:description"), title=data.get("Descrição", ""))
    if desc:
        data["Descrição complementar"] = desc
        data["Descrição curta"] = desc

    category = data.get("Categoria") or _extract_category(soup)
    if category:
        data["Categoria"] = category
        data["Categoria do produto"] = category

    data.update({k: v for k, v in _extract_regex_optional(text).items() if v})

    price = data.get("Preço") or _extract_price_from_page(soup, text)
    if price:
        data["Preço"] = price
        data["Preço unitário"] = data.get("Preço unitário") or price
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
    if gtin:
        data["GTIN/EAN"] = gtin

    images = data.get("URL Imagens Externas") or _first_meta(soup, "og:image", "twitter:image") or _extract_images(soup, page_url)
    if images:
        data["URL Imagens Externas"] = images

    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag and canonical_tag.get("href"):
        canonical = normalize_url(canonical_tag.get("href"), page_url)

    data["Link Externo"] = canonical if is_product_url(canonical) else page_url
    data["URL do Produto"] = data["Link Externo"]
    data["Fonte captura"] = "pagina_produto"

    if not data.get("Estoque"):
        data.pop("Estoque", None)

    return {key: _clean_text(value) for key, value in data.items() if _clean_text(value)}


def crawl_product_pages(
    seed_urls: Iterable[str],
    *,
    max_products: Optional[int] = None,
    use_sitemap: bool = True,
) -> list[dict[str, str]]:
    product_urls = discover_product_urls(seed_urls, max_products=max_products, use_sitemap=use_sitemap)
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


def crawl_product_pages_dataframe(
    seed_urls: Iterable[str],
    *,
    max_products: Optional[int] = None,
    use_sitemap: bool = True,
) -> pd.DataFrame:
    return pd.DataFrame(crawl_product_pages(seed_urls, max_products=max_products, use_sitemap=use_sitemap))
