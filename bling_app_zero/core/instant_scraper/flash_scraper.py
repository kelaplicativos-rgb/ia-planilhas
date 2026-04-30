from __future__ import annotations

import json
import re
from collections import Counter
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
}

CARD_HINTS = (
    "product", "produto", "item", "card", "vitrine", "shelf", "showcase", "catalog", "grid", "listagem",
    "woocommerce", "shopify", "nuvem", "tray", "loja", "catalogo", "produto-card", "collection"
)
BAD_LINK_HINTS = (
    "login", "conta", "account", "carrinho", "cart", "checkout", "whatsapp", "facebook", "instagram", "youtube",
    "politica", "termos", "privacy", "blog", "faq", "atendimento", "contact", "contato"
)
PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d{1,6}\.\d{2})")
CODE_RE = re.compile(r"(?:c[oó]d(?:igo)?|sku|ref(?:er[eê]ncia)?|modelo|item)\s*[:#-]?\s*([A-Za-z0-9._/-]{3,40})", re.I)
GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return " ".join(unescape(tag.get_text(" ", strip=True)).split())


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _fetch_html(url: str, timeout: int = 18) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text or ""
    except Exception:
        return ""


def _same_domain_or_relative(href: str, base_url: str) -> bool:
    try:
        parsed = urlparse(href)
        if not parsed.netloc:
            return True
        return parsed.netloc.replace("www.", "") == urlparse(base_url).netloc.replace("www.", "")
    except Exception:
        return True


def _is_product_link(href: str, base_url: str = "") -> bool:
    h = (href or "").lower().strip()
    if not h or h.startswith("#") or h.startswith("javascript:") or h.startswith("mailto:") or h.startswith("tel:"):
        return False
    if any(bad in h for bad in BAD_LINK_HINTS):
        return False
    if base_url and not _same_domain_or_relative(href, base_url):
        return False
    strong = any(x in h for x in ("produto", "product", "/p/", "/prod/", "/item/", "-p-", "sku", "products/"))
    return strong or len(h.strip("/")) > 10


def _best_link(card: Tag, base_url: str) -> str:
    links = []
    for a in card.find_all("a", href=True):
        href = _clean(a.get("href"))
        if _is_product_link(href, base_url):
            links.append(urljoin(base_url, href))
    return links[0] if links else ""


def _best_image(card: Tag, base_url: str) -> str:
    attrs = ("src", "data-src", "data-original", "data-lazy", "data-image", "data-srcset", "srcset")
    for img in card.find_all(["img", "source"]):
        for attr in attrs:
            src = _clean(img.get(attr, ""))
            if src:
                src = src.split(",")[0].strip().split(" ")[0]
            if src and not src.startswith("data:"):
                return urljoin(base_url, src)
    return ""


def _best_name(card: Tag) -> str:
    selectors = [
        "[itemprop=name]", "h1", "h2", "h3", "h4",
        "[class*=name]", "[class*=nome]", "[class*=title]", "[class*=titulo]",
        "[class*=product-name]", "[class*=produto-nome]", "[class*=desc]",
    ]
    for sel in selectors:
        found = card.select_one(sel)
        txt = _text(found)
        if 5 <= len(txt) <= 180 and not PRICE_RE.search(txt):
            return txt
    alt_titles = []
    for img in card.find_all("img"):
        for attr in ("alt", "title"):
            value = _clean(img.get(attr, ""))
            if 5 <= len(value) <= 180 and not PRICE_RE.search(value):
                alt_titles.append(value)
    if alt_titles:
        return max(alt_titles, key=len)
    link_txts = [_text(a) for a in card.find_all("a")]
    link_txts = [t for t in link_txts if 5 <= len(t) <= 180 and not PRICE_RE.search(t)]
    if link_txts:
        return max(link_txts, key=len)
    txt = _text(card)
    return txt[:180] if txt else ""


def _best_price(card: Tag) -> str:
    candidates = []
    for tag in card.find_all(True):
        cls = " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", ""))
        marker = f"{cls} {tag.get('id', '')} {tag.get('itemprop', '')}".lower()
        if any(x in marker for x in ("price", "preco", "preço", "valor", "amount", "offer")):
            candidates.append(_text(tag))
            if tag.get("content"):
                candidates.append(_clean(tag.get("content")))
    candidates.append(_text(card))
    for txt in candidates:
        m = PRICE_RE.search(txt or "")
        if m:
            return m.group(1)
    return ""


def _best_code(card: Tag) -> str:
    txt = _text(card)
    m = CODE_RE.search(txt)
    if m:
        return m.group(1)
    for attr in ("data-sku", "data-product-sku", "data-id", "data-product-id", "data-item-id", "id"):
        value = _clean(card.get(attr, ""))
        if value and len(value) <= 50:
            return value
    return ""


def _best_gtin(card: Tag) -> str:
    m = GTIN_RE.search(_text(card))
    return m.group(1) if m else ""


def _dom_signature(tag: Tag) -> str:
    classes = tag.get("class", [])
    if isinstance(classes, list):
        classes = ".".join(sorted([str(c) for c in classes if c]))[:80]
    marker = str(classes or tag.get("itemtype", "") or tag.get("data-product-id", ""))
    children = [getattr(c, "name", "") for c in list(tag.children) if getattr(c, "name", "")]
    return f"{tag.name}|{marker}|{'/'.join(children[:8])}"


def _score_card(card: Tag, base_url: str, repeated_signatures: set[str] | None = None) -> int:
    txt = _text(card)
    cls = " ".join(card.get("class", [])) if isinstance(card.get("class"), list) else str(card.get("class", ""))
    ident = str(card.get("id", ""))
    marker = f"{cls} {ident} {card.get('itemtype', '')}".lower()
    score = 0
    if any(h in marker for h in CARD_HINTS):
        score += 3
    if repeated_signatures and _dom_signature(card) in repeated_signatures:
        score += 3
    if _best_link(card, base_url):
        score += 3
    if _best_image(card, base_url):
        score += 2
    if _best_price(card):
        score += 2
    if _best_name(card):
        score += 2
    if 20 <= len(txt) <= 1600:
        score += 1
    if len(txt) > 2500:
        score -= 3
    return score


def _repeated_signatures(tags: list[Tag]) -> set[str]:
    counter = Counter(_dom_signature(t) for t in tags)
    return {sig for sig, count in counter.items() if count >= 3 and sig}


def _candidate_cards(soup: BeautifulSoup, base_url: str) -> list[Tag]:
    tags = soup.find_all(["article", "li", "div", "tr", "section"])
    repeated = _repeated_signatures(tags)
    scored: list[tuple[int, Tag]] = []
    for tag in tags:
        score = _score_card(tag, base_url, repeated)
        if score >= 6:
            scored.append((score, tag))
    scored.sort(key=lambda x: x[0], reverse=True)

    result: list[Tag] = []
    seen: set[str] = set()
    for _, tag in scored:
        link = _best_link(tag, base_url)
        name = _best_name(tag)
        price = _best_price(tag)
        key = link or f"{name}|{price}"
        if not key or key in seen:
            continue
        if len(_text(tag)) > 3000:
            continue
        seen.add(key)
        result.append(tag)
        if len(result) >= 500:
            break
    return result


def _jsonld_products(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for script in soup.find_all("script", type=lambda x: x and "ld+json" in str(x).lower()):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop(0)
            if isinstance(obj, list):
                stack.extend(obj)
                continue
            if not isinstance(obj, dict):
                continue
            graph = obj.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            typ = obj.get("@type")
            typ_txt = " ".join(typ) if isinstance(typ, list) else str(typ or "")
            if "Product" not in typ_txt:
                continue
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            image = obj.get("image")
            if isinstance(image, list):
                image = image[0] if image else ""
            rows.append({
                "Nome": _clean(obj.get("name")),
                "Descrição": _clean(obj.get("description")),
                "SKU": _clean(obj.get("sku") or obj.get("mpn")),
                "GTIN": _clean(obj.get("gtin13") or obj.get("gtin") or obj.get("gtin14") or obj.get("gtin12")),
                "Preço": _clean(offers.get("price") if isinstance(offers, dict) else ""),
                "url_produto": urljoin(base_url, _clean(obj.get("url") or (offers.get("url") if isinstance(offers, dict) else ""))),
                "Imagem URL": urljoin(base_url, _clean(image)),
                "Disponibilidade": _clean(offers.get("availability") if isinstance(offers, dict) else ""),
                "origem_site_status": "flash_jsonld_ok",
                "origem_site_motor": "FLASH_JSONLD",
            })
    return [r for r in rows if r.get("Nome") or r.get("url_produto")]


def _microdata_products(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    rows = []
    for node in soup.select('[itemscope][itemtype*="Product"], [itemtype*="schema.org/Product"]'):
        if not isinstance(node, Tag):
            continue
        name_node = node.select_one('[itemprop="name"]')
        price_node = node.select_one('[itemprop="price"], [itemprop="lowPrice"]')
        sku_node = node.select_one('[itemprop="sku"], [itemprop="mpn"]')
        img_node = node.select_one('[itemprop="image"], img')
        link = _best_link(node, base_url)
        image = ""
        if img_node:
            image = img_node.get("content") or img_node.get("src") or img_node.get("data-src") or ""
        rows.append({
            "Nome": _text(name_node) or _best_name(node),
            "Descrição": _best_name(node),
            "SKU": _text(sku_node) or _best_code(node),
            "GTIN": _best_gtin(node),
            "Preço": _clean(price_node.get("content") if price_node and price_node.get("content") else _text(price_node)) or _best_price(node),
            "url_produto": link,
            "Imagem URL": urljoin(base_url, _clean(image)) if image else _best_image(node, base_url),
            "URL origem da busca": base_url,
            "origem_site_status": "flash_microdata_ok",
            "origem_site_motor": "FLASH_MICRODATA",
        })
    return [r for r in rows if r.get("Nome") or r.get("url_produto")]


def _html_tables(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for tr in soup.select("table tr"):
        cells = [_text(td) for td in tr.find_all(["td", "th"])]
        joined = " | ".join([c for c in cells if c])
        if len(cells) < 2 or not PRICE_RE.search(joined):
            continue
        rows.append({
            "Nome": max(cells, key=len)[:180] if cells else "",
            "Descrição": joined[:500],
            "SKU": _best_code(tr),
            "GTIN": _best_gtin(tr),
            "Preço": _best_price(tr),
            "url_produto": _best_link(tr, base_url),
            "Imagem URL": _best_image(tr, base_url),
            "URL origem da busca": base_url,
            "origem_site_status": "flash_table_ok",
            "origem_site_motor": "FLASH_TABLE",
        })
    return rows


def _og_single_product(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    def meta(*keys: str) -> str:
        for key in keys:
            node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if node and node.get("content"):
                return _clean(node.get("content"))
        return ""

    title = meta("og:title", "twitter:title") or _text(soup.find("title"))
    price = meta("product:price:amount", "og:price:amount")
    image = meta("og:image", "twitter:image")
    if title and (price or image):
        return [{
            "Nome": title,
            "Descrição": meta("og:description", "description") or title,
            "SKU": "",
            "GTIN": "",
            "Preço": price,
            "url_produto": base_url,
            "Imagem URL": urljoin(base_url, image) if image else "",
            "URL origem da busca": base_url,
            "origem_site_status": "flash_meta_ok",
            "origem_site_motor": "FLASH_META",
        }]
    return []


def _card_rows(cards: list[Tag], base_url: str, progress_callback=None, indice_url: int = 1) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    total_cards = max(1, len(cards))
    for i, card in enumerate(cards, start=1):
        if progress_callback and (i == 1 or i % 8 == 0 or i == total_cards):
            progress_callback(min(92, 35 + int((i / total_cards) * 55)), f"FLASH UNIVERSAL: extraindo card {i}/{total_cards}", indice_url)
        nome = _best_name(card)
        link = _best_link(card, base_url)
        imagem = _best_image(card, base_url)
        preco = _best_price(card)
        codigo = _best_code(card)
        gtin = _best_gtin(card)
        if not (nome or link or imagem or preco):
            continue
        rows.append({
            "Nome": nome,
            "Descrição": nome,
            "SKU": codigo,
            "Código": codigo,
            "GTIN": gtin,
            "Preço": preco,
            "url_produto": link,
            "Imagem URL": imagem,
            "URL origem da busca": base_url,
            "origem_site_status": "flash_universal_ok",
            "origem_site_motor": "FLASH_UNIVERSAL_DOM",
        })
    return rows


def run_flash_scraper(
    url: str,
    progress_callback=None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    if progress_callback:
        progress_callback(3, f"FLASH UNIVERSAL: baixando HTML {indice_url}/{total_urls}", indice_url)

    html = _fetch_html(url)
    if not html:
        return pd.DataFrame()

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    if progress_callback:
        progress_callback(12, "FLASH UNIVERSAL: lendo JSON-LD", indice_url)
    rows.extend(_jsonld_products(soup, url))

    if progress_callback:
        progress_callback(22, "FLASH UNIVERSAL: lendo microdados/schema.org", indice_url)
    rows.extend(_microdata_products(soup, url))

    if progress_callback:
        progress_callback(30, "FLASH UNIVERSAL: lendo meta tags/OpenGraph", indice_url)
    rows.extend(_og_single_product(soup, url))

    if progress_callback:
        progress_callback(38, "FLASH UNIVERSAL: procurando tabelas HTML", indice_url)
    rows.extend(_html_tables(soup, url))

    if progress_callback:
        progress_callback(45, "FLASH UNIVERSAL: detectando repetição DOM estilo Instant Data Scraper", indice_url)
    cards = _candidate_cards(soup, url)
    rows.extend(_card_rows(cards, url, progress_callback, indice_url))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")
    for col in ("url_produto", "Nome", "SKU", "Código", "GTIN"):
        if col in df.columns:
            df[col] = df[col].astype(str).map(_clean)
    subset = [c for c in ["url_produto", "Nome", "SKU"] if c in df.columns]
    if subset:
        df = df.drop_duplicates(subset=subset, keep="first")
    df["URL origem da busca"] = url
    return df.reset_index(drop=True)
