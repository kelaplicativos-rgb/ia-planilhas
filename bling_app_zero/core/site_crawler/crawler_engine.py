from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        texto = str(valor).strip()
    except Exception:
        return ""

    if texto.lower() in {"none", "nan", "null"}:
        return ""

    texto = unescape(texto)
    texto = texto.replace("\ufeff", "").replace("\x00", "")
    texto = re.sub(r"[\r\n\t]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _primeiro(*valores: Any) -> str:
    for valor in valores:
        texto = _safe_str(valor)
        if texto:
            return texto
    return ""


def _normalizar_preco(valor: Any) -> str:
    if valor is None:
        return ""

    if isinstance(valor, (int, float)):
        numero = float(valor)
        if numero <= 0:
            return ""
        return f"{numero:.2f}".replace(".", ",")

    texto = _safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace("r$", "").strip()
    texto = re.sub(r"[^\d,.\-]", "", texto)

    if not texto:
        return ""

    if "," in texto and "." in texto:
        texto_float = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto_float = texto.replace(",", ".")
    else:
        texto_float = texto

    try:
        numero = float(texto_float)
        if numero <= 0:
            return ""
        return f"{numero:.2f}".replace(".", ",")
    except Exception:
        return ""


def _normalizar_gtin(valor: Any) -> str:
    numeros = re.sub(r"\D", "", _safe_str(valor))
    if len(numeros) in {8, 12, 13, 14}:
        return numeros
    return ""


def _normalizar_estoque(valor: Any) -> int:
    if isinstance(valor, bool):
        return int(valor)

    if isinstance(valor, (int, float)):
        return max(int(valor), 0)

    texto = _safe_str(valor).lower()

    if not texto:
        return 0

    if any(
        termo in texto
        for termo in [
            "sem estoque",
            "indisponível",
            "indisponivel",
            "esgotado",
            "zerado",
            "out of stock",
            "sold out",
            "unavailable",
        ]
    ):
        return 0

    match = re.search(r"(\d+)", texto)
    if match:
        try:
            return max(int(match.group(1)), 0)
        except Exception:
            return 0

    if any(
        termo in texto
        for termo in [
            "disponível",
            "disponivel",
            "em estoque",
            "in stock",
            "available",
            "comprar",
        ]
    ):
        return 1

    return 0


def _limpar_nome(nome: Any) -> str:
    texto = _safe_str(nome)
    texto = re.sub(r"\s*[-|]\s*Mega Center.*$", "", texto, flags=re.I)
    texto = re.sub(r"\s*[-|]\s*Comprar.*$", "", texto, flags=re.I)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _json_loads_seguro(texto: str) -> Any:
    texto = _safe_str(texto)
    if not texto:
        return None

    try:
        return json.loads(texto)
    except Exception:
        pass

    try:
        texto = re.sub(r"[\x00-\x1f]+", " ", texto)
        texto = texto.strip()
        return json.loads(texto)
    except Exception:
        return None


def _flatten_jsonld(data: Any) -> List[Dict[str, Any]]:
    itens: List[Dict[str, Any]] = []

    if isinstance(data, list):
        for item in data:
            itens += _flatten_jsonld(item)

    elif isinstance(data, dict):
        itens.append(data)

        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                itens += _flatten_jsonld(item)

    return itens


def _extrair_jsonld(soup: BeautifulSoup) -> Dict[str, Any]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = script.string or script.get_text(" ", strip=True)
        data = _json_loads_seguro(bruto)
        if not data:
            continue

        for item in _flatten_jsonld(data):
            tipo = item.get("@type") or item.get("type") or ""
            tipo_txt = " ".join(tipo) if isinstance(tipo, list) else str(tipo)

            if "product" in tipo_txt.lower():
                return item

    return {}


def _extrair_meta(soup: BeautifulSoup, *nomes: str) -> str:
    for nome in nomes:
        meta = (
            soup.find("meta", attrs={"property": nome})
            or soup.find("meta", attrs={"name": nome})
            or soup.find("meta", attrs={"itemprop": nome})
        )
        if meta and meta.get("content"):
            return _safe_str(meta.get("content"))
    return ""


def _extrair_por_seletores(soup: BeautifulSoup, seletores: List[str]) -> str:
    for seletor in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = el.get_text(" ", strip=True)
                if texto:
                    return _safe_str(texto)
                valor = el.get("content") or el.get("value") or el.get("data-price")
                if valor:
                    return _safe_str(valor)
        except Exception:
            continue
    return ""


def _resolver_imagem(src: str, base_url: str) -> str:
    src = _safe_str(src)
    if not src:
        return ""
    if src.startswith("//"):
        src = "https:" + src
    return urljoin(base_url, src)


def _imagem_valida(url: str) -> bool:
    u = _safe_str(url).lower()

    if not u:
        return False

    bloqueios = [
        "logo",
        "placeholder",
        "sprite",
        "icon",
        "favicon",
        "banner",
        "whatsapp",
        "facebook",
        "instagram",
        "youtube",
        "pixel",
        "tracking",
        "loader",
        "blank",
    ]

    if any(b in u for b in bloqueios):
        return False

    return any(ext in u for ext in [".jpg", ".jpeg", ".png", ".webp", "/image/", "cdn"])


def _extrair_imagens(soup: BeautifulSoup, base_url: str, jsonld: Dict[str, Any]) -> List[str]:
    imagens: List[str] = []

    img_json = jsonld.get("image") if isinstance(jsonld, dict) else None

    if isinstance(img_json, list):
        imagens += [_resolver_imagem(x, base_url) for x in img_json]
    elif img_json:
        imagens.append(_resolver_imagem(str(img_json), base_url))

    meta_img = _extrair_meta(soup, "og:image", "twitter:image")
    if meta_img:
        imagens.append(_resolver_imagem(meta_img, base_url))

    for img in soup.find_all("img"):
        candidatos = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-original"),
            img.get("data-lazy"),
            img.get("data-zoom-image"),
            img.get("srcset"),
        ]

        for src in candidatos:
            if not src:
                continue

            src = str(src)

            if "," in src:
                src = src.split(",")[0]

            if " " in src:
                src = src.split(" ")[0]

            imagens.append(_resolver_imagem(src, base_url))

    final = []
    vistos = set()

    for img in imagens:
        img = _safe_str(img)
        if not _imagem_valida(img):
            continue
        if img in vistos:
            continue
        vistos.add(img)
        final.append(img)

    return final[:12]


def _extrair_preco_jsonld(jsonld: Dict[str, Any]) -> str:
    offers = jsonld.get("offers") if isinstance(jsonld, dict) else None

    if isinstance(offers, list) and offers:
        offers = offers[0]

    if isinstance(offers, dict):
        price_spec = offers.get("priceSpecification")
        price_spec_price = ""

        if isinstance(price_spec, dict):
            price_spec_price = price_spec.get("price")
        elif isinstance(price_spec, list) and price_spec:
            primeiro = price_spec[0]
            if isinstance(primeiro, dict):
                price_spec_price = primeiro.get("price")

        return _normalizar_preco(
            offers.get("price")
            or offers.get("lowPrice")
            or offers.get("highPrice")
            or price_spec_price
        )

    return ""


def _extrair_estoque_jsonld(jsonld: Dict[str, Any]) -> int:
    offers = jsonld.get("offers") if isinstance(jsonld, dict) else None

    if isinstance(offers, list) and offers:
        offers = offers[0]

    if isinstance(offers, dict):
        disponibilidade = _safe_str(offers.get("availability"))
        return _normalizar_estoque(disponibilidade)

    return 0


def _extrair_sku_texto(texto: str) -> str:
    padroes = [
        r"\bSKU[:\s#-]*([A-Z0-9._/-]{3,60})",
        r"\bC[ÓO]D(?:IGO)?[:\s#-]*([A-Z0-9._/-]{3,60})",
        r"\bREF(?:ER[ÊE]NCIA)?[:\s#-]*([A-Z0-9._/-]{3,60})",
        r"\bMODELO[:\s#-]*([A-Z0-9._/-]{3,60})",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto or "", flags=re.I)
        if match:
            return _safe_str(match.group(1))

    return ""


def _extrair_gtin_texto(texto: str) -> str:
    padroes = [
        r"\bGTIN[:\s#-]*(\d{8,14})",
        r"\bEAN[:\s#-]*(\d{8,14})",
        r"c[óo]digo de barras[:\s#-]*(\d{8,14})",
        r"\b(\d{13})\b",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto or "", flags=re.I)
        if match:
            gtin = _normalizar_gtin(match.group(1))
            if gtin:
                return gtin

    return ""


def _extrair_categoria(soup: BeautifulSoup, jsonld: Dict[str, Any]) -> str:
    categoria_json = _safe_str(jsonld.get("category")) if isinstance(jsonld, dict) else ""
    if categoria_json:
        return categoria_json

    itens = []

    for seletor in [
        ".breadcrumb a",
        ".breadcrumbs a",
        "[class*='breadcrumb'] a",
        "nav[aria-label*='breadcrumb'] a",
        "[class*='categoria'] a",
    ]:
        try:
            for el in soup.select(seletor):
                txt = _safe_str(el.get_text(" ", strip=True))
                if txt and txt.lower() not in {"home", "início", "inicio"}:
                    itens.append(txt)
        except Exception:
            continue

    vistos = []
    for item in itens:
        if item not in vistos:
            vistos.append(item)

    return " > ".join(vistos)


def extract_product_from_page(html, url):
    html = html or ""
    soup = BeautifulSoup(html, "lxml")

    jsonld = _extrair_jsonld(soup)
    texto_pagina = soup.get_text(" ", strip=True)

    nome = _primeiro(
        jsonld.get("name") if isinstance(jsonld, dict) else "",
        _extrair_meta(soup, "og:title", "twitter:title"),
        _extrair_por_seletores(
            soup,
            [
                "h1",
                "[class*='product-title']",
                "[class*='produto-titulo']",
                "[class*='product-name']",
                "[class*='nome-produto']",
                "[data-testid*='product-title']",
                "[itemprop='name']",
            ],
        ),
        soup.title.get_text(" ", strip=True) if soup.title else "",
    )

    preco = _primeiro(
        _extrair_preco_jsonld(jsonld),
        _extrair_meta(
            soup,
            "product:price:amount",
            "og:price:amount",
            "twitter:data1",
        ),
        _extrair_por_seletores(
            soup,
            [
                "[itemprop='price']",
                "[data-price]",
                "[class*='price']",
                "[class*='preco']",
                "[class*='valor']",
                "[class*='money']",
            ],
        ),
    )

    sku = _primeiro(
        jsonld.get("sku") if isinstance(jsonld, dict) else "",
        jsonld.get("mpn") if isinstance(jsonld, dict) else "",
        _extrair_meta(soup, "product:retailer_item_id"),
        _extrair_sku_texto(texto_pagina),
    )

    marca = ""
    brand = jsonld.get("brand") if isinstance(jsonld, dict) else ""

    if isinstance(brand, dict):
        marca = _safe_str(brand.get("name"))
    else:
        marca = _safe_str(brand)

    gtin = _primeiro(
        jsonld.get("gtin") if isinstance(jsonld, dict) else "",
        jsonld.get("gtin8") if isinstance(jsonld, dict) else "",
        jsonld.get("gtin12") if isinstance(jsonld, dict) else "",
        jsonld.get("gtin13") if isinstance(jsonld, dict) else "",
        jsonld.get("gtin14") if isinstance(jsonld, dict) else "",
        _extrair_gtin_texto(texto_pagina),
    )

    descricao = _primeiro(
        jsonld.get("description") if isinstance(jsonld, dict) else "",
        _extrair_meta(soup, "og:description", "description", "twitter:description"),
        _extrair_por_seletores(
            soup,
            [
                "[class*='description']",
                "[class*='descricao']",
                "[id*='description']",
                "[id*='descricao']",
                "[itemprop='description']",
            ],
        ),
    )

    categoria = _extrair_categoria(soup, jsonld)
    imagens = _extrair_imagens(soup, url, jsonld)

    estoque = _extrair_estoque_jsonld(jsonld)
    if estoque == 0:
        estoque = _normalizar_estoque(texto_pagina)

    nome_limpo = _limpar_nome(nome)

    return {
        "nome": nome_limpo,
        "preco": _normalizar_preco(preco),
        "url": url,
        "url_produto": url,
        "sku": sku,
        "marca": marca,
        "categoria": categoria,
        "estoque": estoque,
        "gtin": _normalizar_gtin(gtin),
        "descricao": descricao,
        "imagens": imagens,
    }
