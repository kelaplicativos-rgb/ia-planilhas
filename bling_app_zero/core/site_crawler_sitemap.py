
from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

try:
    from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
except Exception:
    def normalizar_url(url: str) -> str:
        url = str(url or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url.rstrip("/")

    def safe_str(value: Any) -> str:
        return str(value or "").strip()

try:
    from bling_app_zero.core.site_supplier_profiles import get_supplier_profile
except Exception:
    def get_supplier_profile(url: str):
        return None


# ============================================================
# CONFIG
# ============================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,text/plain,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

MOBILE_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
}

SITEMAP_CANDIDATE_PATHS = [
    "/robots.txt",
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap/sitemap.xml",
    "/sitemap/products.xml",
    "/sitemap_produtos.xml",
    "/product-sitemap.xml",
    "/produto-sitemap.xml",
    "/produtos-sitemap.xml",
    "/post-sitemap.xml",
    "/page-sitemap.xml",
    "/category-sitemap.xml",
    "/categoria-sitemap.xml",
    "/sitemaps.xml",
]

PRODUCT_SITEMAP_HINTS = [
    "product",
    "produto",
    "produtos",
    "products",
    "catalog",
    "catalogo",
    "shop",
    "store",
    "item",
    "sku",
    "inventory",
    "estoque",
]

CATEGORY_SITEMAP_HINTS = [
    "category",
    "categories",
    "categoria",
    "categorias",
    "collection",
    "collections",
    "departamento",
    "departamentos",
    "taxonomy",
    "terms",
]

BAD_SITEMAP_HINTS = [
    "post",
    "posts",
    "page",
    "pages",
    "blog",
    "news",
    "noticia",
    "noticias",
    "image",
    "images",
    "video",
    "videos",
    "author",
    "tag",
    "tags",
]

URL_PRODUCT_HINTS = [
    "/produto/",
    "/product/",
    "/products/",
    "/p/",
    "/item/",
    "/sku/",
    "/prd/",
]

CATEGORY_HINTS = [
    "/categoria",
    "/categorias",
    "/departamento",
    "/collection",
    "/collections",
    "/search",
    "/busca",
]

BAD_URL_HINTS = [
    "/login",
    "/conta",
    "/account",
    "/checkout",
    "/cart",
    "/carrinho",
    "/politica",
    "/privacy",
    "/terms",
    "/contato",
    "/sobre",
    "/blog",
    "mailto:",
    "javascript:",
]

ASSET_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
    ".css", ".js", ".mjs", ".map", ".pdf", ".zip",
    ".xml", ".txt", ".json", ".ico", ".woff", ".woff2",
    ".ttf", ".eot",
}


# ============================================================
# LOG
# ============================================================

def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
        return
    except Exception:
        pass

    try:
        print(f"[SITE_CRAWLER_SITEMAP][{nivel}] {msg}")
    except Exception:
        pass


# ============================================================
# HELPERS
# ============================================================

def _normalizar_base(url: str) -> str:
    url_n = normalizar_url(url)
    parsed = urlparse(url_n)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url_n


def _dominio(url: str) -> str:
    try:
        return safe_str(urlparse(url).netloc).lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_dominio(base_url: str, url: str) -> bool:
    return bool(_dominio(base_url) and _dominio(base_url) == _dominio(url))


def _path_url(url: str) -> str:
    try:
        return safe_str(urlparse(url).path).lower()
    except Exception:
        return ""


def _query_url(url: str) -> str:
    try:
        return safe_str(urlparse(url).query).lower()
    except Exception:
        return ""


def _profile(url: str):
    try:
        return get_supplier_profile(url)
    except Exception:
        return None


def _profile_product_keywords(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "product_url_keywords", ()) or ())


def _profile_category_keywords(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "category_url_keywords", ()) or ())


def _profile_category_hints(url: str) -> tuple[str, ...]:
    profile = _profile(url)
    if profile is None:
        return ()
    return tuple(getattr(profile, "category_path_hints", ()) or ())


def _url_tem_extensao_asset(url: str) -> bool:
    path = _path_url(url)
    return any(path.endswith(ext) for ext in ASSET_EXTENSIONS)


def _url_ruim(url: str) -> bool:
    url_n = safe_str(url).lower()
    if not url_n:
        return True

    if any(h in url_n for h in BAD_URL_HINTS):
        return True

    if _url_tem_extensao_asset(url_n):
        return True

    return False


def _url_eh_categoria(url: str) -> bool:
    url_n = safe_str(url).lower()
    if not url_n:
        return False

    if any(h in url_n for h in CATEGORY_HINTS):
        return True

    for hint in _profile_category_hints(url):
        hint_n = safe_str(hint).lower()
        if hint_n and hint_n in url_n:
            return True

    for token in _profile_category_keywords(url):
        token_n = safe_str(token).lower()
        if token_n and token_n in url_n:
            return True

    return False


def _url_parece_produto(url: str) -> bool:
    url_n = safe_str(url).lower()
    if not url_n:
        return False

    if _url_ruim(url_n):
        return False

    if any(h in url_n for h in URL_PRODUCT_HINTS):
        return True

    for token in _profile_product_keywords(url):
        token_n = safe_str(token).lower()
        if token_n and token_n in url_n:
            return True

    if _url_eh_categoria(url_n):
        return False

    ultimo_slug = safe_str(urlparse(url_n).path.split("/")[-1])
    if ultimo_slug and "-" in ultimo_slug and len(ultimo_slug) >= 8:
        return True

    return False


def _score_url_produto(url: str) -> int:
    url_n = safe_str(url).lower()
    if not url_n:
        return -999

    if _url_ruim(url_n):
        return -999

    score = 0

    if any(h in url_n for h in URL_PRODUCT_HINTS):
        score += 8

    for token in _profile_product_keywords(url):
        token_n = safe_str(token).lower()
        if token_n and token_n in url_n:
            score += 4

    if _url_eh_categoria(url_n):
        score -= 6

    if re.search(r"/p/[\w\-]+", url_n):
        score += 3

    if re.search(r"/produto/[\w\-]+", url_n):
        score += 3

    if re.search(r"/product/[\w\-]+", url_n):
        score += 3

    ultimo_slug = safe_str(urlparse(url_n).path.split("/")[-1])
    if ultimo_slug and "-" in ultimo_slug and len(ultimo_slug) >= 10:
        score += 2

    return score


def _score_sitemap_url(url: str) -> int:
    url_n = safe_str(url).lower()
    if not url_n:
        return -999

    score = 0

    if "robots.txt" in url_n:
        score += 1
    if "sitemap" in url_n:
        score += 2
    if url_n.endswith(".xml") or url_n.endswith(".gz"):
        score += 1

    if any(h in url_n for h in PRODUCT_SITEMAP_HINTS):
        score += 7

    if any(h in url_n for h in CATEGORY_SITEMAP_HINTS):
        score -= 5

    if any(h in url_n for h in BAD_SITEMAP_HINTS):
        score -= 7

    return score


def _deduplicar_preservando_ordem(urls: list[str]) -> list[str]:
    saida: list[str] = []
    vistos: set[str] = set()

    for url in urls:
        url_n = safe_str(url)
        if not url_n or url_n in vistos:
            continue
        vistos.add(url_n)
        saida.append(url_n)

    return saida


def _request_bytes(url: str, timeout: int = 40) -> bytes:
    ultima_exc: Exception | None = None

    for headers in (DEFAULT_HEADERS, MOBILE_HEADERS):
        for verify in (True, False):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=verify,
                )
                if response.ok and response.content:
                    return response.content
                ultima_exc = RuntimeError(f"HTTP {response.status_code}")
            except Exception as exc:
                ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return b""


def _decode_sitemap_bytes(content: bytes, url: str = "") -> str:
    if not content:
        return ""

    try:
        if safe_str(url).lower().endswith(".gz"):
            with gzip.GzipFile(fileobj=BytesIO(content)) as gz:
                raw = gz.read()
            for encoding in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    return raw.decode(encoding, errors="ignore")
                except Exception:
                    continue
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        pass

    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding, errors="ignore")
        except Exception:
            continue

    return ""


def _parse_xml(texto_xml: str) -> ET.Element | None:
    xml = safe_str(texto_xml)
    if not xml:
        return None

    try:
        return ET.fromstring(xml)
    except Exception:
        pass

    try:
        xml_limpo = re.sub(r"^\s*<\?xml[^>]*\?>", "", xml, flags=re.I)
        return ET.fromstring(xml_limpo)
    except Exception:
        return None


def _tag_local(element: ET.Element) -> str:
    try:
        return safe_str(element.tag).split("}")[-1].lower()
    except Exception:
        return ""


def _child_text(element: ET.Element, child_tag_local: str) -> str:
    try:
        for child in list(element):
            if _tag_local(child) == child_tag_local:
                return safe_str(child.text)
    except Exception:
        return ""
    return ""


def _guess_product_sitemap(url: str) -> bool:
    url_n = safe_str(url).lower()
    if not url_n:
        return False
    if any(h in url_n for h in BAD_SITEMAP_HINTS):
        return False
    if any(h in url_n for h in PRODUCT_SITEMAP_HINTS):
        return True
    return False


def _guess_bad_sitemap(url: str) -> bool:
    url_n = safe_str(url).lower()
    return any(h in url_n for h in BAD_SITEMAP_HINTS)


# ============================================================
# ROBOTS / DESCOBERTA
# ============================================================

def extrair_sitemaps_do_robots(base_url: str) -> list[str]:
    base = _normalizar_base(base_url)
    robots_url = f"{base}/robots.txt"

    sitemaps: list[str] = []

    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        found = getattr(rp, "site_maps", lambda: None)()
        if isinstance(found, list):
            for url in found:
                url_n = normalizar_url(url)
                if url_n:
                    sitemaps.append(url_n)
    except Exception as exc:
        _log_debug(f"Falha ao ler robots.txt com parser | url={robots_url} | erro={exc}", nivel="ERRO")

    if sitemaps:
        return _deduplicar_preservando_ordem(sitemaps)

    try:
        content = _request_bytes(robots_url, timeout=25)
        texto = _decode_sitemap_bytes(content, robots_url)
        if texto:
            for line in texto.splitlines():
                line_n = safe_str(line)
                if not line_n:
                    continue
                if line_n.lower().startswith("sitemap:"):
                    url = safe_str(line_n.split(":", 1)[1])
                    if url:
                        sitemaps.append(normalizar_url(url))
    except Exception as exc:
        _log_debug(f"Falha ao buscar robots.txt bruto | url={robots_url} | erro={exc}", nivel="ERRO")

    return _deduplicar_preservando_ordem(sitemaps)


def descobrir_urls_sitemap(base_url: str) -> list[str]:
    base = _normalizar_base(base_url)
    candidatas = [f"{base}{path}" for path in SITEMAP_CANDIDATE_PATHS if path != "/robots.txt"]
    robots = extrair_sitemaps_do_robots(base)

    urls = robots + candidatas
    urls = _deduplicar_preservando_ordem(urls)
    urls.sort(key=_score_sitemap_url, reverse=True)
    return urls


# ============================================================
# LEITURA DE SITEMAP
# ============================================================

def ler_sitemap_xml(url_sitemap: str) -> tuple[list[str], list[str]]:
    """
    Retorna:
    - sub_sitemaps encontrados em sitemapindex
    - urls encontradas em urlset
    """
    url_sitemap = safe_str(url_sitemap)
    if not url_sitemap:
        return [], []

    try:
        content = _request_bytes(url_sitemap)
        texto = _decode_sitemap_bytes(content, url_sitemap)
    except Exception as exc:
        _log_debug(f"Falha ao baixar sitemap | url={url_sitemap} | erro={exc}", nivel="ERRO")
        return [], []

    root = _parse_xml(texto)
    if root is None:
        _log_debug(f"XML inválido ou não parseável | url={url_sitemap}", nivel="ERRO")
        return [], []

    root_tag = _tag_local(root)

    sub_sitemaps: list[str] = []
    urls: list[str] = []

    if root_tag == "sitemapindex":
        for item in list(root):
            if _tag_local(item) != "sitemap":
                continue
            loc = _child_text(item, "loc")
            if loc:
                sub_sitemaps.append(normalizar_url(loc))

    elif root_tag == "urlset":
        for item in list(root):
            if _tag_local(item) != "url":
                continue
            loc = _child_text(item, "loc")
            if loc:
                urls.append(normalizar_url(loc))

    else:
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", texto, flags=re.I | re.S):
            loc_n = normalizar_url(loc)
            if not loc_n:
                continue
            if "sitemap" in loc_n.lower() and loc_n.lower().endswith((".xml", ".gz")):
                sub_sitemaps.append(loc_n)
            else:
                urls.append(loc_n)

    return _deduplicar_preservando_ordem(sub_sitemaps), _deduplicar_preservando_ordem(urls)


def expandir_sitemaps(base_url: str, max_sitemaps: int = 50, max_urls_total: int = 50000) -> list[str]:
    base = _normalizar_base(base_url)
    fila = descobrir_urls_sitemap(base)
    fila = _deduplicar_preservando_ordem(fila)

    sitemaps_visitados: set[str] = set()
    urls_final: list[str] = []
    urls_vistas: set[str] = set()

    while fila:
        if len(sitemaps_visitados) >= max_sitemaps:
            break
        if len(urls_final) >= max_urls_total:
            break

        fila.sort(key=_score_sitemap_url, reverse=True)

        sitemap_atual = fila.pop(0)
        sitemap_atual = safe_str(sitemap_atual)
        if not sitemap_atual or sitemap_atual in sitemaps_visitados:
            continue

        sitemaps_visitados.add(sitemap_atual)

        sub_sitemaps, urls = ler_sitemap_xml(sitemap_atual)

        sub_sitemaps = _deduplicar_preservando_ordem(sub_sitemaps)
        sub_sitemaps.sort(key=_score_sitemap_url, reverse=True)

        for sub in sub_sitemaps:
            if sub in sitemaps_visitados or sub in fila:
                continue
            if _guess_bad_sitemap(sub) and not _guess_product_sitemap(sub):
                continue
            fila.append(sub)

        for url in urls:
            if not _mesmo_dominio(base, url):
                continue
            if url in urls_vistas:
                continue
            urls_vistas.add(url)
            urls_final.append(url)
            if len(urls_final) >= max_urls_total:
                break

    return _deduplicar_preservando_ordem(urls_final)


# ============================================================
# FILTRO DE PRODUTOS
# ============================================================

def filtrar_urls_produto_de_sitemap(base_url: str, urls: list[str], limite: int = 8000) -> list[str]:
    base = _normalizar_base(base_url)

    candidatos: list[tuple[int, str]] = []

    for url in urls:
        url_n = safe_str(url)
        if not url_n:
            continue
        if not _mesmo_dominio(base, url_n):
            continue
        if _url_ruim(url_n):
            continue

        score = _score_url_produto(url_n)

        path = _path_url(url_n)
        query = _query_url(url_n)

        if _url_eh_categoria(url_n):
            score -= 5

        if "page=" in query or "pagina=" in query or "offset=" in query or "/page/" in path:
            score -= 2

        if score < 2 and not _url_parece_produto(url_n):
            continue

        candidatos.append((score, url_n))

    candidatos.sort(key=lambda item: item[0], reverse=True)

    saida: list[str] = []
    vistos: set[str] = set()

    for score, url in candidatos:
        if score < 2:
            continue
        if url in vistos:
            continue
        vistos.add(url)
        saida.append(url)
        if len(saida) >= limite:
            break

    return saida


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def descobrir_produtos_via_sitemap(
    base_url: str,
    limite: int = 8000,
    max_sitemaps: int = 50,
    max_urls_total: int = 50000,
) -> list[str]:
    base = _normalizar_base(base_url)
    if not base:
        return []

    _log_debug(
        f"Iniciando descoberta via sitemap | url={base} | limite={limite} | max_sitemaps={max_sitemaps}",
        nivel="INFO",
    )

    try:
        urls_sitemap = expandir_sitemaps(
            base_url=base,
            max_sitemaps=max_sitemaps,
            max_urls_total=max_urls_total,
        )
    except Exception as exc:
        _log_debug(f"Falha ao expandir sitemaps | url={base} | erro={exc}", nivel="ERRO")
        return []

    if not urls_sitemap:
        _log_debug(f"Nenhuma URL encontrada em sitemap | url={base}", nivel="INFO")
        return []

    produtos = filtrar_urls_produto_de_sitemap(
        base_url=base,
        urls=urls_sitemap,
        limite=limite,
    )

    _log_debug(
        f"Descoberta via sitemap finalizada | url={base} | urls_total={len(urls_sitemap)} | produtos={len(produtos)}",
        nivel="INFO",
    )

    return produtos


# ============================================================
# DIAGNÓSTICO OPCIONAL
# ============================================================

def diagnostico_sitemap(base_url: str) -> dict[str, Any]:
    base = _normalizar_base(base_url)

    candidatas = descobrir_urls_sitemap(base)
    urls_brutas = expandir_sitemaps(base, max_sitemaps=30, max_urls_total=40000)
    produtos = filtrar_urls_produto_de_sitemap(base, urls_brutas, limite=5000)

    urls_ruins = 0
    urls_categoria = 0
    urls_produto_forte = 0

    for url in urls_brutas[:5000]:
        if _url_ruim(url):
            urls_ruins += 1
        if _url_eh_categoria(url):
            urls_categoria += 1
        if _url_parece_produto(url):
            urls_produto_forte += 1

    return {
        "base_url": base,
        "sitemaps_candidatos": candidatas,
        "urls_encontradas_total": len(urls_brutas),
        "produtos_filtrados_total": len(produtos),
        "urls_ruins_total": urls_ruins,
        "urls_categoria_total": urls_categoria,
        "urls_produto_forte_total": urls_produto_forte,
        "amostra_produtos": produtos[:20],
    }
