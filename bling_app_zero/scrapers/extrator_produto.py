from __future__ import annotations

import json
import re
from html import unescape
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup


PRODUCT_URL_HINTS = (
    "/produto",
    "/product",
    "/p/",
    "/pd-",
    "/shop/",
    "/item/",
    "/sku/",
)

CATEGORY_URL_HINTS = (
    "/categoria",
    "/categorias",
    "/category",
    "/departamento",
    "/colecao",
    "/colecoes",
    "/collections",
    "/catalog",
    "/loja/",
    "/shop/",
)

PRODUCT_IMAGE_SELECTORS = [
    ".woocommerce-product-gallery img",
    ".product-gallery img",
    ".product__gallery img",
    ".product-gallery__image img",
    ".produto-galeria img",
    ".galeria-produto img",
    ".gallery img",
    ".swiper img",
    ".slick-slide img",
    "[data-fancybox] img",
    "[data-zoom-image]",
    "[data-large_image]",
    "[class*=product] img",
    "[class*=produto] img",
    "[class*=gallery] img",
    "[class*=galeria] img",
    "[id*=product] img",
    "[id*=produto] img",
    "[itemprop=image]",
]

TRACKING_HOST_TOKENS = (
    "facebook.com",
    "facebook.net",
    "google-analytics.com",
    "googletagmanager.com",
    "googleads.g.doubleclick.net",
    "doubleclick.net",
    "analytics",
    "hotjar",
    "clarity",
    "pixel.",
    "trk.",
)

TRACKING_PATH_TOKENS = (
    "/tr",
    "/track",
    "/tracking",
    "/events",
    "/collect",
    "/pixel",
)

BAD_IMAGE_TOKENS = (
    "sprite",
    "icon",
    "logo",
    "banner",
    "avatar",
    "placeholder",
    "spacer",
    "blank.",
    "loader",
    "loading",
    "favicon",
    "lazyload",
    "thumb",
    "thumbnail",
    "mini",
    "small",
)

GOOD_IMAGE_HINTS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
    "/produto/",
    "/produtos/",
    "/product/",
    "/products/",
    "/uploads/",
    "/media/",
    "/images/",
    "/image/",
    "/cdn/",
    "data-large_image",
    "zoom",
)


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = unescape(str(value)).replace("\xa0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _only_digits(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\D+", "", str(value))


def _to_price(value: Optional[str]) -> str:
    txt = _clean_text(value)
    if not txt:
        return ""

    txt = txt.replace("R$", "").replace("r$", "").replace(" ", "")
    txt = re.sub(r"[^0-9,.\-]", "", txt)

    if txt.count(",") == 1 and txt.count(".") >= 1:
        txt = txt.replace(".", "").replace(",", ".")
    elif txt.count(",") == 1 and txt.count(".") == 0:
        txt = txt.replace(",", ".")

    return txt


def _pick_first(*values) -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                txt = _clean_text(item)
                if txt:
                    return txt
        else:
            txt = _clean_text(value)
            if txt:
                return txt
    return ""


def _extract_json_objects(raw: str) -> List[dict]:
    if not raw:
        return []

    raw = raw.strip()
    candidatos = [raw]

    if "\n" in raw:
        candidatos.extend([linha.strip() for linha in raw.splitlines() if linha.strip()])

    objetos: List[dict] = []

    for candidato in candidatos:
        try:
            data = json.loads(candidato)
        except Exception:
            continue

        blocos = data if isinstance(data, list) else [data]
        for bloco in blocos:
            if isinstance(bloco, dict):
                objetos.append(bloco)

    return objetos


def _iter_product_objects(obj) -> Iterable[dict]:
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_product_objects(item)
        return

    if not isinstance(obj, dict):
        return

    tipo = str(obj.get("@type", "")).lower()

    if tipo == "product" or "product" in tipo.split(","):
        yield obj

    grafo = obj.get("@graph")
    if isinstance(grafo, list):
        for item in grafo:
            yield from _iter_product_objects(item)

    for chave in ("mainEntity", "itemListElement"):
        valor = obj.get(chave)
        if isinstance(valor, (list, dict)):
            yield from _iter_product_objects(valor)


def _parse_json_ld(soup: BeautifulSoup) -> Dict:
    produtos: List[Dict] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)

        for bloco in _extract_json_objects(raw):
            produtos.extend(list(_iter_product_objects(bloco)))

    if not produtos:
        return {}

    p = produtos[0]

    offers = p.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}

    brand = p.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name", "")

    images = p.get("image", [])
    if isinstance(images, str):
        images = [images]
    if not isinstance(images, list):
        images = []

    category = p.get("category", "")
    if isinstance(category, list):
        category = " > ".join(_clean_text(x) for x in category if _clean_text(x))

    sku = p.get("sku") or p.get("mpn") or ""
    gtin = (
        p.get("gtin13")
        or p.get("gtin12")
        or p.get("gtin14")
        or p.get("gtin8")
        or p.get("gtin")
        or ""
    )

    return {
        "nome": _clean_text(p.get("name", "")),
        "descricao_curta": _clean_text(p.get("description", "")),
        "marca": _clean_text(brand),
        "codigo": _clean_text(sku),
        "gtin": _only_digits(gtin),
        "preco": _to_price(offers.get("price")),
        "moeda": _clean_text(offers.get("priceCurrency", "")),
        "disponibilidade": _clean_text(offers.get("availability", "")),
        "categoria": _clean_text(category),
        "imagens": [_clean_text(x) for x in images if _clean_text(x)],
    }


def _extract_meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return _clean_text(tag["content"])

    tag = soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return _clean_text(tag["content"])

    return ""


def _find_price_in_text(html: str) -> str:
    padroes = [
        r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}",
        r"R\$\s?\d+,\d{2}",
        r"price[^0-9]{0,10}(\d+[\.,]\d{2})",
    ]

    for padrao in padroes:
        achados = re.findall(padrao, html or "", flags=re.IGNORECASE)
        if achados:
            valor = achados[0] if isinstance(achados[0], str) else achados[0][0]
            return _to_price(valor)

    return ""


def _find_gtin_in_text(html: str) -> str:
    padroes = [
        r"gtin[^0-9]{0,20}([0-9]{8,14})",
        r"ean[^0-9]{0,20}([0-9]{8,14})",
        r"barcode[^0-9]{0,20}([0-9]{8,14})",
    ]

    texto = html or ""

    for padrao in padroes:
        achados = re.findall(padrao, texto, flags=re.IGNORECASE)
        if achados:
            return _only_digits(achados[0])

    return ""


def _normalizar_url_imagem(url: str, base_url: str) -> str:
    txt = _clean_text(url)
    if not txt:
        return ""

    if txt.startswith("data:image"):
        return ""

    if "," in txt:
        partes = [p.strip() for p in txt.split(",") if p.strip()]
        for parte in partes:
            primeira = parte.split(" ")[0].strip()
            if primeira:
                txt = primeira
                break

    absoluto = urljoin(base_url, txt).strip()
    if not absoluto.startswith(("http://", "https://")):
        return ""

    return absoluto


def _eh_url_tracking(url: str) -> bool:
    try:
        baixa = _clean_text(url).lower()
        if not baixa:
            return True

        parsed = urlparse(baixa)
        host = parsed.netloc or ""
        path = parsed.path or ""
        query = parsed.query or ""

        if any(token in host for token in TRACKING_HOST_TOKENS):
            return True

        if any(token in path for token in TRACKING_PATH_TOKENS):
            return True

        if any(token in query for token in ("fbclid", "gclid", "utm_", "pixel", "track")):
            return True

        return False
    except Exception:
        return True


def _eh_url_imagem_ruim(url: str) -> bool:
    try:
        baixa = _clean_text(url).lower()
        if not baixa:
            return True

        if _eh_url_tracking(baixa):
            return True

        if any(token in baixa for token in BAD_IMAGE_TOKENS):
            return True

        return False
    except Exception:
        return True


def _score_imagem(url: str, base_url: str, contexto: str = "") -> int:
    try:
        baixa = _clean_text(url).lower()
        if not baixa:
            return -999

        if _eh_url_imagem_ruim(baixa):
            return -999

        score = 0

        base_host = (urlparse(base_url).netloc or "").lower()
        host = (urlparse(baixa).netloc or "").lower()

        if host and base_host and host == base_host:
            score += 6
        elif host.endswith(base_host) and base_host:
            score += 4

        if any(token in baixa for token in GOOD_IMAGE_HINTS):
            score += 5

        if any(token in baixa for token in ("/produto/", "/produtos/", "/product/", "/products/")):
            score += 4

        contexto_low = (contexto or "").lower()
        if any(token in contexto_low for token in ("gallery", "galeria", "product", "produto", "zoom")):
            score += 5

        if "og:image" in contexto_low:
            score += 3

        if "twitter:image" in contexto_low:
            score += 1

        path = urlparse(baixa).path or ""
        if re.search(r"\.(jpg|jpeg|png|webp|gif|avif)$", path, flags=re.IGNORECASE):
            score += 4

        if "facebook.com/tr" in baixa:
            score -= 1000

        return score
    except Exception:
        return -999
