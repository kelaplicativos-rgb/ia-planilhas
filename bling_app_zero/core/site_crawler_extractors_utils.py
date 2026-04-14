from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    meta_content_crawler,
    numero_texto_crawler,
    texto_limpo_crawler,
)

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


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _extrair_preco_global(html: str) -> str:
    matches = re.findall(r"R\$\s*\d[\d\.\,]*", html or "", re.I)
    for match in matches:
        preco = numero_texto_crawler(match)
        if preco:
            return preco
    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    try:
        for nav in soup.select("nav, .breadcrumb, [class*='bread']"):
            textos = [texto_limpo_crawler(x.get_text()) for x in nav.select("a, span")]
            textos = [t for t in textos if t and len(t) < 40]
            if len(textos) >= 2:
                return " > ".join(textos[:4])
    except Exception:
        pass
    return ""


def _limpar_descricao(texto: str) -> str:
    if not texto:
        return ""

    cortes = [
        "mega center eletrônicos",
        "produtos relacionados",
        "veja também",
        "formas de pagamento",
        "atendimento",
        "loja física",
        "endereço",
    ]

    txt = texto.lower()
    for corte in cortes:
        txt = txt.split(corte)[0]

    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()[:800]


def _normalizar_url_imagem(url: str, base_url: str) -> str:
    txt = _safe_str(url)
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
        baixa = _safe_str(url).lower()
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
        baixa = _safe_str(url).lower()
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
        baixa = _safe_str(url).lower()
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

        contexto_low = _safe_str(contexto).lower()
        if any(token in contexto_low for token in ("gallery", "galeria", "product", "produto", "zoom")):
            score += 5
        if "og:image" in contexto_low:
            score += 3
        if "twitter:image" in contexto_low:
            score += 1

        path = urlparse(baixa).path or ""
        if re.search(r"\.(jpg|jpeg|png|webp|gif|avif)$", path, flags=re.I):
            score += 4

        if "facebook.com/tr" in baixa:
            score -= 1000

        return score
    except Exception:
        return -999


def _adicionar_url_imagem(
    urls: list[str],
    url: str,
    base_url: str,
    contexto: str = "",
    min_score: int = 0,
) -> None:
    normalizada = _normalizar_url_imagem(url, base_url)
    if not normalizada:
        return

    if _score_imagem(normalizada, base_url, contexto) < min_score:
        return

    if normalizada not in urls:
        urls.append(normalizada)


def _filtrar_imagens(lista: list[str]) -> str:
    if not lista:
        return ""

    urls: list[str] = []
    vistos: set[str] = set()

    for item in lista:
        img = _safe_str(item)
        if not img or img in vistos:
            continue
        vistos.add(img)
        urls.append(img)

    return " | ".join(urls[:5])


def _meta_og_title(soup: BeautifulSoup) -> str:
    return meta_content_crawler(soup, "property", "og:title")
