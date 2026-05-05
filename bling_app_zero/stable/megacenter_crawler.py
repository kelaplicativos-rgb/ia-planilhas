from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TIMEOUT = 18
MAX_PAGES = 120
MAX_PRODUCTS = 800
MAX_CART_PROBE = 200

KNOWN_BRANDS = [
    "JBL", "Samsung", "Apple", "Xiaomi", "Motorola", "LG", "Sony", "Philips", "Multilaser",
    "Lenovo", "Dell", "HP", "Asus", "Acer", "Intelbras", "Positivo", "Mondial", "Britânia",
    "Britania", "Elgin", "Aiwa", "Havit", "Baseus", "Amazfit", "Haylou", "Lenoxx", "Knup",
    "Exbom", "Inova", "Kaidi", "Tomate", "MXT", "Importado", "B-Max", "Bmax", "Gshield",
]


@dataclass
class CrawlConfig:
    estoque_padrao: int = 1
    max_pages: int = MAX_PAGES
    max_products: int = MAX_PRODUCTS
    simular_carrinho: bool = True
    max_cart_probe: int = MAX_CART_PROBE


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + str(url or "").strip())
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def _same_domain(url: str, domain: str) -> bool:
    return urlparse(url).netloc.replace("www.", "") == domain.replace("www.", "")


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


def _fetch(url: str, session: requests.Session | None = None) -> str:
    sess = session or _new_session()
    response = sess.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _absolute(base: str, href: str) -> str:
    return _normalize_url(urljoin(base, href or ""))


def _is_product_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/produto/" in path or "/product/" in path


def _should_follow(url: str) -> bool:
    path = urlparse(url).path.lower()
    blocked = ["/carrinho", "/checkout", "/login", "/conta", "whatsapp", "mailto:", "tel:"]
    return not any(item in url.lower() or item in path for item in blocked)


def _discover_links(start_urls: list[str], config: CrawlConfig) -> list[str]:
    if not start_urls:
        return []

    domain = urlparse(start_urls[0]).netloc.replace("www.", "")
    queue: deque[str] = deque(start_urls)
    visited: set[str] = set()
    product_urls: list[str] = []
    product_seen: set[str] = set()
    session = _new_session()

    while queue and len(visited) < config.max_pages and len(product_urls) < config.max_products:
        url = _normalize_url(queue.popleft())
        if url in visited or not _same_domain(url, domain) or not _should_follow(url):
            continue
        visited.add(url)

        try:
            html = _fetch(url, session=session)
        except Exception:
            continue

        soup = _soup(html)
        for a in soup.find_all("a", href=True):
            href = _absolute(url, str(a.get("href") or ""))
            if not _same_domain(href, domain) or not _should_follow(href):
                continue
            if _is_product_url(href):
                if href not in product_seen:
                    product_seen.add(href)
                    product_urls.append(href)
                    if len(product_urls) >= config.max_products:
                        break
            elif len(visited) + len(queue) < config.max_pages:
                queue.append(href)

    return product_urls


def _safe_json(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _walk_json(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk_json(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _extract_json_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        payload = _safe_json(raw or "")
        if payload is not None:
            for item in _walk_json(payload):
                if isinstance(item, dict):
                    objects.append(item)

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        payload = _safe_json(next_data.string or next_data.get_text(" ", strip=True) or "")
        if payload is not None:
            for item in _walk_json(payload):
                if isinstance(item, dict):
                    objects.append(item)

    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ", strip=False)
        if not raw or ("produto" not in raw.lower() and "product" not in raw.lower()):
            continue
        for match in re.findall(r"\{[^{}]{20,3000}\}", raw):
            payload = _safe_json(match)
            if isinstance(payload, dict):
                objects.append(payload)

    return objects


def _first_meta(soup: BeautifulSoup, names: Iterable[str]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(tag.get("content"))
    return ""


def _json_first(objects: list[dict[str, Any]], keys: Iterable[str]) -> str:
    normalized = {k.lower() for k in keys}
    for obj in objects:
        for key, value in obj.items():
            if str(key).lower() in normalized and value not in (None, "", [], {}):
                if isinstance(value, dict):
                    for sub_key in ("name", "nome", "title", "titulo"):
                        if value.get(sub_key):
                            return _clean_text(value.get(sub_key))
                    continue
                if isinstance(value, list):
                    continue
                return _clean_text(value)
    return ""


def _json_first_number(objects: list[dict[str, Any]], keys: Iterable[str]) -> int | None:
    value = _json_first(objects, keys)
    if not value:
        return None
    found = re.search(r"\d+", value)
    if not found:
        return None
    try:
        return max(0, int(found.group(0)))
    except Exception:
        return None


def _json_product_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for obj in objects:
        obj_type = str(obj.get("@type") or obj.get("type") or "").lower()
        keys = {str(k).lower() for k in obj.keys()}
        if "product" in obj_type or {"name", "sku"}.issubset(keys) or "gtin" in " ".join(keys):
            products.append(obj)
    return products or objects


def _extract_images(soup: BeautifulSoup, base_url: str, objects: list[dict[str, Any]]) -> str:
    images: list[str] = []
    seen: set[str] = set()

    meta_image = _first_meta(soup, ["og:image", "twitter:image"])
    if meta_image:
        images.append(_absolute(base_url, meta_image))

    for obj in objects:
        for key, value in obj.items():
            if str(key).lower() not in {"image", "images", "imagem", "imagens", "urlimage", "url_image"}:
                continue
            if isinstance(value, str):
                images.append(_absolute(base_url, value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        images.append(_absolute(base_url, item))
                    elif isinstance(item, dict):
                        candidate = item.get("url") or item.get("src") or item.get("image")
                        if candidate:
                            images.append(_absolute(base_url, str(candidate)))

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy")
        if not src:
            continue
        images.append(_absolute(base_url, str(src)))

    cleaned: list[str] = []
    for url in images:
        low = url.lower()
        if any(
            skip in low
            for skip in [
                "facebook.com/tr",
                "analytics",
                "pixel",
                "logo",
                "sprite",
                "placeholder",
                "loading",
                "whatsapp",
                "icon",
                "favicon",
            ]
        ):
            continue
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return "|".join(cleaned[:12])


def _extract_code(text: str, url: str, objects: list[dict[str, Any]]) -> str:
    json_code = _json_first(objects, ["sku", "codigo", "código", "code", "reference", "referencia", "referência", "id"])
    if json_code:
        return json_code[:60]

    patterns = [
        r"C[ÓO]D\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"SKU\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"REF\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))[:60]
    parts = [p for p in urlparse(url).path.split("/") if p]
    if parts:
        first = re.match(r"(\d+)", parts[-1])
        if first:
            return first.group(1)[:60]
        return re.sub(r"[^A-Za-z0-9_-]+", "-", parts[-1]).strip("-")[:60]
    return ""


def _extract_gtin(text: str, objects: list[dict[str, Any]]) -> str:
    json_gtin = _json_first(objects, ["gtin", "gtin8", "gtin12", "gtin13", "gtin14", "ean", "barcode", "codigoBarras"])
    if json_gtin:
        digits = re.sub(r"\D+", "", json_gtin)
        if len(digits) in {8, 12, 13, 14}:
            return digits

    candidates = re.findall(r"\b\d{8,14}\b", text)
    for candidate in candidates:
        if len(candidate) in {8, 12, 13, 14}:
            return candidate
    return ""


def _format_money_from_any(value: object) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    if re.search(r"\d+\.\d{1,2}$", raw):
        try:
            return f"{float(raw):.2f}".replace(".", ",")
        except Exception:
            pass
    money = re.search(r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{1,2})", raw)
    if not money:
        return ""
    found = money.group(1)
    if "." in found and "," not in found:
        try:
            return f"{float(found):.2f}".replace(".", ",")
        except Exception:
            return found
    return found


def _extract_prices(text: str, objects: list[dict[str, Any]]) -> tuple[str, str]:
    preco_venda = _format_money_from_any(
        _json_first(objects, ["price", "salePrice", "sale_price", "preco", "preço", "valor", "valorVenda"])
    )

    prices = re.findall(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{1,2})", text)
    normal = [_format_money_from_any(p) for p in prices if _format_money_from_any(p)]

    if not preco_venda and normal:
        preco_venda = normal[-1] if len(normal) > 1 else normal[0]

    # Regra solicitada: preço de custo capturado por site deve ficar em branco.
    return preco_venda, ""


def _extract_product_id(url: str, html: str, objects: list[dict[str, Any]]) -> str:
    for source in [_json_first(objects, ["id", "productId", "product_id", "produtoId", "produto_id"]), url]:
        found = re.search(r"\b(\d{4,})\b", str(source or ""))
        if found:
            return found.group(1)

    patterns = [
        r"product[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
        r"produto[_-]?id[\"']?\s*[:=]\s*[\"']?(\d+)",
        r"data-product-id=[\"'](\d+)[\"']",
        r"data-produto-id=[\"'](\d+)[\"']",
        r"data-id=[\"'](\d+)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _cart_response_allows(response: requests.Response) -> bool:
    text = response.text.lower()
    if response.status_code >= 400:
        return False
    negative = ["sem estoque", "indispon", "quantidade indispon", "não disponível", "nao dispon", "esgotado", "erro"]
    return not any(term in text for term in negative)


def _try_cart_quantity(session: requests.Session, product_url: str, product_id: str, quantity: int) -> bool | None:
    if not product_id or quantity <= 0:
        return None

    base = f"{urlparse(product_url).scheme}://{urlparse(product_url).netloc}"
    endpoints = [
        "/carrinho/adicionar",
        "/carrinho/add",
        "/cart/add",
        "/checkout/cart/add",
        "/api/carrinho/adicionar",
        "/api/cart/add",
        "/api/cart",
    ]
    id_keys = ["produto_id", "product_id", "id_produto", "id", "sku"]
    qty_keys = ["quantidade", "quantity", "qtd", "qty"]

    for endpoint in endpoints:
        url = urljoin(base, endpoint)
        for id_key in id_keys:
            for qty_key in qty_keys:
                payload = {id_key: product_id, qty_key: quantity}
                try:
                    response = session.post(url, data=payload, timeout=TIMEOUT, allow_redirects=False)
                    if response.status_code in {404, 405, 403}:
                        continue
                    return _cart_response_allows(response)
                except Exception:
                    continue
    return None


def _probe_cart_stock(session: requests.Session, product_url: str, product_id: str, config: CrawlConfig) -> int | None:
    if not config.simular_carrinho or not product_id:
        return None

    first = _try_cart_quantity(session, product_url, product_id, 1)
    if first is not True:
        return None

    low = 1
    high = 2
    max_probe = max(1, int(config.max_cart_probe or MAX_CART_PROBE))

    while high <= max_probe:
        ok = _try_cart_quantity(session, product_url, product_id, high)
        if ok is True:
            low = high
            high *= 2
            continue
        if ok is False:
            break
        return low

    high = min(high, max_probe)
    while low < high:
        mid = (low + high + 1) // 2
        ok = _try_cart_quantity(session, product_url, product_id, mid)
        if ok is True:
            low = mid
        elif ok is False:
            high = mid - 1
        else:
            break
    return low


def _availability_from_text(text: str, html: str, objects: list[dict[str, Any]]) -> tuple[str, bool | None]:
    json_availability = _json_first(objects, ["availability", "disponibilidade", "available", "isAvailable"])
    low_json = json_availability.lower()
    if any(term in low_json for term in ["instock", "in stock", "dispon", "true", "sim"]):
        return "Disponível", True
    if any(term in low_json for term in ["outofstock", "out of stock", "esgot", "indispon", "false", "nao", "não"]):
        return "Indisponível", False

    page = (html + " " + text).lower()
    has_buy = any(term in page for term in ["comprar agora", ">comprar<", "adicionar ao carrinho", "colocar no carrinho"])
    has_unavailable = any(term in page for term in ["esgotado", "sem estoque", "indisponível", "indisponivel", "fora de estoque", "avise-me"])

    if has_buy:
        return "Disponível", True
    if has_unavailable:
        return "Indisponível", False
    return "Não identificado", None


def _extract_real_stock(text: str, html: str, objects: list[dict[str, Any]]) -> int | None:
    stock_json = _json_first_number(
        objects,
        [
            "stock",
            "estoque",
            "quantity",
            "quantidade",
            "availableStock",
            "inventoryQuantity",
            "saldo",
            "maxQuantity",
        ],
    )
    if stock_json is not None:
        return stock_json

    explicit_patterns = [
        r"estoque[^0-9]{0,30}(\d{1,5})",
        r"quantidade[^0-9]{0,30}(\d{1,5})",
        r"availableStock[^0-9]{0,30}(\d{1,5})",
        r"inventoryQuantity[^0-9]{0,30}(\d{1,5})",
        r"stock[^0-9]{0,30}(\d{1,5})",
        r"max=[\"'](\d{1,5})[\"']",
        r"data-stock=[\"'](\d{1,5})[\"']",
        r"data-estoque=[\"'](\d{1,5})[\"']",
    ]
    haystack = html + "\n" + text
    for pattern in explicit_patterns:
        match = re.search(pattern, haystack, flags=re.IGNORECASE)
        if match:
            try:
                return max(0, int(match.group(1)))
            except Exception:
                pass
    return None


def _resolve_stock(text: str, html: str, objects: list[dict[str, Any]], availability_label: str, available: bool | None) -> int:
    real_stock = _extract_real_stock(text, html, objects)
    if real_stock is not None:
        return int(real_stock)
    if available is False or availability_label == "Indisponível":
        return 0
    if available is True or availability_label == "Disponível":
        return 1
    return 0


def _extract_category(soup: BeautifulSoup, objects: list[dict[str, Any]]) -> str:
    json_category = _json_first(objects, ["category", "categoria", "categoryName", "nomeCategoria"])
    if json_category:
        return json_category

    bits: list[str] = []
    selectors = ["nav a", ".breadcrumb a", "[class*=breadcrumb] a", "[class*=categoria] a"]
    for selector in selectors:
        for tag in soup.select(selector):
            txt = _clean_text(tag.get_text(" ", strip=True))
            if txt and txt.lower() not in {"home", "início", "inicio", "produtos"} and txt not in bits:
                bits.append(txt)
    return " > ".join(bits[:5])


def _extract_raw_description(soup: BeautifulSoup, objects: list[dict[str, Any]]) -> str:
    json_description = _json_first(objects, ["description", "descricao", "descrição", "shortDescription", "longDescription"])
    if json_description:
        return json_description[:2000]

    candidates: list[str] = []
    for selector in ["[class*=descricao]", "[class*=description]", "section", "article"]:
        for tag in soup.select(selector):
            txt = _clean_text(tag.get_text(" ", strip=True))
            if len(txt) > 30:
                candidates.append(txt)
    if candidates:
        return max(candidates, key=len)[:2000]
    return _first_meta(soup, ["description", "og:description"])[:2000]


def _extract_brand_from_title(title: str) -> str:
    haystack = f" {title} "
    for known in KNOWN_BRANDS:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(known)}(?![A-Za-z0-9])", haystack, flags=re.IGNORECASE):
            return known.upper() if known.lower() == "jbl" else known
    return ""


def _extract_product(url: str, config: CrawlConfig) -> dict[str, object] | None:
    session = _new_session()
    try:
        html = _fetch(url, session=session)
    except Exception:
        return None

    soup = _soup(html)
    objects_all = _extract_json_objects(soup)
    objects = _json_product_objects(objects_all)
    text = _clean_text(soup.get_text(" ", strip=True))

    title = _json_first(objects, ["name", "title", "titulo", "título"])
    title = title or _first_meta(soup, ["og:title", "twitter:title"])
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" ", strip=True)) or title

    codigo = _extract_code(text, url, objects)
    gtin = _extract_gtin(text, objects)
    preco_venda, preco_custo = _extract_prices(text, objects)
    product_id = _extract_product_id(url, html, objects)
    raw_description = _extract_raw_description(soup, objects)
    marca = _extract_brand_from_title(title)
    availability_label, available = _availability_from_text(text, html, objects_all)
    estoque = _resolve_stock(text, html, objects, availability_label, available)

    cart_stock = _probe_cart_stock(session, url, product_id or codigo, config)
    if cart_stock is not None:
        estoque = cart_stock
        availability_label = "Disponível" if cart_stock > 0 else "Indisponível"

    if availability_label == "Não identificado":
        availability_label = "Disponível" if int(estoque) > 0 else "Indisponível"

    imagens = _extract_images(soup, url, objects_all)
    categoria = _extract_category(soup, objects_all)
    descricao_complementar = raw_description

    if not title and not codigo:
        return None

    return {
        "Código": codigo or gtin or product_id,
        "Descrição": title or codigo or product_id,
        "Descrição complementar": descricao_complementar,
        "Unidade": "UN",
        "NCM": "",
        "GTIN/EAN": gtin,
        "Preço unitário": preco_venda,
        "Preço de custo": preco_custo,
        "Marca": marca,
        "Categoria": categoria,
        "URL imagens externas": imagens,
        "Estoque": int(estoque),
        "Quantidade": int(estoque),
        "URL do produto": url,
        "Disponibilidade": availability_label,
        "Produto ID site": product_id,
        "Origem": "site",
    }


def crawl_site_to_bling_dataframe(raw_urls: str, estoque_padrao: int = 1) -> pd.DataFrame:
    start_urls = [_normalize_url(u) for u in re.split(r"[\n,;\s]+", str(raw_urls or "")) if str(u).strip()]
    if not start_urls:
        return pd.DataFrame()

    config = CrawlConfig(estoque_padrao=max(0, int(estoque_padrao or 0)))
    product_urls: list[str] = []
    for url in start_urls:
        if _is_product_url(url):
            product_urls.append(url)
    product_urls.extend(_discover_links(start_urls, config))

    ordered: list[str] = []
    seen: set[str] = set()
    for url in product_urls:
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    rows: list[dict[str, object]] = []
    for product_url in ordered[: config.max_products]:
        item = _extract_product(product_url, config)
        if item:
            rows.append(item)

    return pd.DataFrame(rows).fillna("")
