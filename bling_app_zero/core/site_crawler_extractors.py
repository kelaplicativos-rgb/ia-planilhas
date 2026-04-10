from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    buscar_produto_jsonld_crawler,
    detectar_estoque_crawler,
    extrair_json_ld_crawler,
    meta_content_crawler,
    numero_texto_crawler,
    primeiro_texto_crawler,
    todas_imagens_crawler,
    texto_limpo_crawler,
)

# IA
try:
    from bling_app_zero.core.ia_extractor import extrair_com_ia
except Exception:
    extrair_com_ia = None


# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


# ==========================================================
# CONSTANTES
# ==========================================================
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


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _extrair_preco_global(html: str) -> str:
    matches = re.findall(r"R\$\s*\d[\d\.\,]*", html or "", re.I)
    for m in matches:
        p = numero_texto_crawler(m)
        if p:
            return p
    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    for nav in soup.select("nav, .breadcrumb, [class*='bread']"):
        textos = [texto_limpo_crawler(x.get_text()) for x in nav.select("a, span")]
        textos = [t for t in textos if t and len(t) < 40]
        if len(textos) >= 2:
            return " > ".join(textos[:4])
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

    texto = texto.lower()
    for c in cortes:
        texto = texto.split(c)[0]

    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()[:800]


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


def _extrair_imagens_por_selectors(soup: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []

    for selector in PRODUCT_IMAGE_SELECTORS:
        try:
            elementos = soup.select(selector)
        except Exception:
            elementos = []

        for el in elementos:
            candidatos = [
                el.get("src"),
                el.get("data-src"),
                el.get("data-original"),
                el.get("data-lazy"),
                el.get("data-zoom-image"),
                el.get("data-large_image"),
                el.get("href"),
                el.get("srcset"),
            ]

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=selector,
                    min_score=4,
                )

    return urls


def _coletar_imagens_produto(soup: BeautifulSoup, base_url: str, jsonld: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    # JSON-LD
    imagens_json = jsonld.get("image")
    if isinstance(imagens_json, str):
        imagens_json = [imagens_json]
    if isinstance(imagens_json, list):
        for item in imagens_json:
            _adicionar_url_imagem(
                urls=urls,
                url=_safe_str(item),
                base_url=base_url,
                contexto="json-ld",
                min_score=1,
            )

    # Metas
    for meta_name in ("og:image", "twitter:image"):
        meta_url = meta_content_crawler(soup, "property", meta_name) or meta_content_crawler(soup, "name", meta_name)
        _adicionar_url_imagem(
            urls=urls,
            url=meta_url,
            base_url=base_url,
            contexto=meta_name,
            min_score=2,
        )

    # Seletores de galeria
    for url in _extrair_imagens_por_selectors(soup, base_url):
        if url not in urls:
            urls.append(url)

    # Fallback do helper legado
    if len(urls) < 2:
        todas = _safe_str(todas_imagens_crawler(soup, base_url))
        for item in [p.strip() for p in todas.split("|") if p.strip()]:
            _adicionar_url_imagem(
                urls=urls,
                url=item,
                base_url=base_url,
                contexto="helper_fallback",
                min_score=5,
            )

    # Fallback final: img geral com filtro rígido
    if len(urls) < 2:
        for img in soup.find_all("img"):
            candidatos = [
                img.get("src"),
                img.get("data-src"),
                img.get("data-original"),
                img.get("data-lazy"),
                img.get("data-zoom-image"),
                img.get("data-large_image"),
                img.get("srcset"),
            ]

            classes = " ".join(img.get("class", []) or [])
            alt = _safe_str(img.get("alt"))
            parent_class = ""
            try:
                parent = img.parent
                if parent:
                    parent_class = " ".join(parent.get("class", []) or [])
            except Exception:
                parent_class = ""

            contexto = " ".join([classes, alt, parent_class]).strip()

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=contexto,
                    min_score=6,
                )

    return urls[:8]


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


# ==========================================================
# EXTRAÇÃO PRINCIPAL
# ==========================================================
def extrair_nome(soup, jsonld):
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            [
                "h1",
                ".product-title",
                ".product-name",
                "[class*='product'] h1",
                "[class*='title']",
            ],
        )
    )


def extrair_preco(soup, jsonld, html):
    offers = jsonld.get("offers")

    if isinstance(offers, dict):
        preco = numero_texto_crawler(offers.get("price"))
        if preco:
            return preco

    if isinstance(offers, list):
        for o in offers:
            preco = numero_texto_crawler(o.get("price"))
            if preco:
                return preco

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        return numero_texto_crawler(meta)

    for el in soup.select("[class*='price'], [class*='valor']"):
        txt = texto_limpo_crawler(el.get_text())
        preco = numero_texto_crawler(txt)
        if preco and len(preco) >= 3:
            return preco

    return _extrair_preco_global(html)


def extrair_descricao(soup, jsonld):
    desc = texto_limpo_crawler(jsonld.get("description"))

    if not desc:
        meta = meta_content_crawler(soup, "name", "description")
        desc = meta or ""

    if not desc:
        for sel in [
            ".product-description",
            ".description",
            "[class*='description']",
        ]:
            el = soup.select_one(sel)
            if el:
                desc = texto_limpo_crawler(el.get_text())
                break

    return _limpar_descricao(desc)


def extrair_imagens(soup, url, jsonld):
    imagens = _coletar_imagens_produto(soup, url, jsonld or {})
    return _filtrar_imagens(imagens)


def extrair_marca(jsonld):
    marca = jsonld.get("brand")
    if isinstance(marca, dict):
        return texto_limpo_crawler(marca.get("name"))
    if isinstance(marca, str):
        return texto_limpo_crawler(marca)
    return ""


# ==========================================================
# MAIN COM IA
# ==========================================================
def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
    network_records=None,
    payload_origem=None,
) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    jsonlds = extrair_json_ld_crawler(soup)
    json_produto = buscar_produto_jsonld_crawler(jsonlds)

    nome = extrair_nome(soup, json_produto)
    preco = extrair_preco(soup, json_produto, html)

    # ======================================================
    # IA FALLBACK
    # ======================================================
    if extrair_com_ia and (not nome or not preco):
        log_debug(f"[IA FALLBACK] {url}")
        produto_ia = extrair_com_ia(html, url)
        if produto_ia and produto_ia.get("Nome"):
            produto_ia["Descrição Curta"] = produto_ia.get("Descrição") or produto_ia.get("Nome")
            return produto_ia

    if not nome:
        return {}

    base = {
        "Nome": nome,
        "Preço": preco,
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(json_produto),
        "Categoria": _extrair_categoria(soup),
        "GTIN/EAN": _digitos(
            json_produto.get("gtin13")
            or json_produto.get("gtin12")
            or json_produto.get("gtin14")
            or json_produto.get("gtin8")
            or json_produto.get("gtin")
        ),
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    log_debug(f"[EXTRACTOR FINAL] {url}")
    return base
