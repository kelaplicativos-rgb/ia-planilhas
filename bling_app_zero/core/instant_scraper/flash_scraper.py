from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin

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
    "product", "produto", "item", "card", "vitrine", "shelf", "showcase", "catalog", "grid", "listagem"
)
BAD_LINK_HINTS = (
    "login", "conta", "carrinho", "checkout", "whatsapp", "facebook", "instagram", "youtube", "politica", "termos"
)
PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")
CODE_RE = re.compile(r"(?:c[oó]d(?:igo)?|sku|ref(?:er[eê]ncia)?|modelo)\s*[:#-]?\s*([A-Za-z0-9._/-]{3,40})", re.I)


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


def _is_product_link(href: str) -> bool:
    h = (href or "").lower()
    if not h or h.startswith("#") or h.startswith("javascript:") or h.startswith("mailto:"):
        return False
    if any(bad in h for bad in BAD_LINK_HINTS):
        return False
    return any(x in h for x in ("produto", "product", "/p/", "/prod/", "-p", "item")) or len(h.strip("/")) > 8


def _best_link(card: Tag, base_url: str) -> str:
    links = []
    for a in card.find_all("a", href=True):
        href = _clean(a.get("href"))
        if _is_product_link(href):
            links.append(urljoin(base_url, href))
    return links[0] if links else ""


def _best_image(card: Tag, base_url: str) -> str:
    for img in card.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy") or ""
        src = _clean(src)
        if src and not src.startswith("data:"):
            return urljoin(base_url, src)
    return ""


def _best_name(card: Tag) -> str:
    selectors = [
        "h1", "h2", "h3", "h4",
        "[class*=name]", "[class*=nome]", "[class*=title]", "[class*=titulo]",
        "[class*=product-name]", "[class*=produto-nome]",
    ]
    for sel in selectors:
        found = card.select_one(sel)
        txt = _text(found)
        if 5 <= len(txt) <= 180 and not PRICE_RE.search(txt):
            return txt
    link_txts = [_text(a) for a in card.find_all("a")]
    link_txts = [t for t in link_txts if 5 <= len(t) <= 180 and not PRICE_RE.search(t)]
    if link_txts:
        return max(link_txts, key=len)
    txt = _text(card)
    if txt:
        return txt[:180]
    return ""


def _best_price(card: Tag) -> str:
    attrs = []
    for tag in card.find_all(True):
        cls = " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", ""))
        if any(x in cls.lower() for x in ("price", "preco", "valor")):
            attrs.append(_text(tag))
    candidates = attrs + [_text(card)]
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
    for attr in ("data-sku", "data-product-sku", "data-id", "data-product-id", "id"):
        value = _clean(card.get(attr, ""))
        if value:
            return value
    return ""


def _score_card(card: Tag, base_url: str) -> int:
    txt = _text(card)
    cls = " ".join(card.get("class", [])) if isinstance(card.get("class"), list) else str(card.get("class", ""))
    ident = str(card.get("id", ""))
    marker = f"{cls} {ident}".lower()
    score = 0
    if any(h in marker for h in CARD_HINTS):
        score += 3
    if _best_link(card, base_url):
        score += 3
    if _best_image(card, base_url):
        score += 2
    if _best_price(card):
        score += 2
    if 20 <= len(txt) <= 1200:
        score += 1
    return score


def _candidate_cards(soup: BeautifulSoup, base_url: str) -> list[Tag]:
    tags = soup.find_all(["article", "li", "div"])
    scored: list[tuple[int, Tag]] = []
    for tag in tags:
        score = _score_card(tag, base_url)
        if score >= 5:
            scored.append((score, tag))
    scored.sort(key=lambda x: x[0], reverse=True)

    result: list[Tag] = []
    seen_links: set[str] = set()
    for _, tag in scored:
        link = _best_link(tag, base_url)
        name = _best_name(tag)
        key = link or name
        if not key or key in seen_links:
            continue
        seen_links.add(key)
        result.append(tag)
        if len(result) >= 300:
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
                "origem_site_motor": "FLASH_JSONLD",
            })
    return [r for r in rows if r.get("Nome") or r.get("url_produto")]


def run_flash_scraper(
    url: str,
    progress_callback=None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    if progress_callback:
        progress_callback(3, f"FLASH: baixando HTML da listagem {indice_url}/{total_urls}", indice_url)

    html = _fetch_html(url)
    if not html:
        return pd.DataFrame()

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    if progress_callback:
        progress_callback(18, "FLASH: lendo JSON-LD e scripts de produto", indice_url)
    rows.extend(_jsonld_products(soup, url))

    if progress_callback:
        progress_callback(35, "FLASH: detectando cards repetidos estilo Instant Data Scraper", indice_url)
    cards = _candidate_cards(soup, url)

    total_cards = max(1, len(cards))
    for i, card in enumerate(cards, start=1):
        if progress_callback and (i == 1 or i % 8 == 0 or i == total_cards):
            progress_callback(min(92, 35 + int((i / total_cards) * 55)), f"FLASH: extraindo card {i}/{total_cards}", indice_url)
        nome = _best_name(card)
        link = _best_link(card, url)
        imagem = _best_image(card, url)
        preco = _best_price(card)
        codigo = _best_code(card)
        if not (nome or link or imagem or preco):
            continue
        rows.append({
            "Nome": nome,
            "Descrição": nome,
            "SKU": codigo,
            "Código": codigo,
            "Preço": preco,
            "url_produto": link,
            "Imagem URL": imagem,
            "URL origem da busca": url,
            "origem_site_status": "flash_ok",
            "origem_site_motor": "FLASH_INSTANT",
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")
    for col in ("url_produto", "Nome", "SKU", "Código"):
        if col in df.columns:
            df[col] = df[col].astype(str).map(_clean)
    subset = [c for c in ["url_produto", "Nome", "SKU"] if c in df.columns]
    if subset:
        df = df.drop_duplicates(subset=subset, keep="first")
    df["URL origem da busca"] = url
    return df.reset_index(drop=True)
