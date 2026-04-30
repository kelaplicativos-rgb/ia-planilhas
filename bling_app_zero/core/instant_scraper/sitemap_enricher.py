from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup


@dataclass
class SitemapCrawlStats:
    sitemap_lidos: int = 0
    urls_sitemap: int = 0
    urls_produto: int = 0
    paginas_processadas: int = 0
    produtos_extraidos: int = 0
    categorias_processadas: int = 0
    urls_visitadas: int = 0
    motivo: str = ""
    erros: list[str] = field(default_factory=list)


def _txt(valor: Any) -> str:
    return str(valor or "").replace("\xa0", " ").strip()


def normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.split("#", 1)[0].rstrip("/")


def _host(url: str) -> str:
    return urlparse(normalizar_url(url)).netloc.replace("www.", "")


def mesmo_host(a: str, b: str) -> bool:
    return bool(_host(a) and _host(a) == _host(b))


def raiz_site(url: str) -> str:
    parsed = urlparse(normalizar_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def sitemap_candidates(base_url: str) -> list[str]:
    root = raiz_site(base_url)
    return [
        f"{root}/sitemap.xml",
        f"{root}/sitemap_index.xml",
        f"{root}/sitemap-produtos.xml",
        f"{root}/sitemap_products.xml",
        f"{root}/product-sitemap.xml",
        f"{root}/products-sitemap.xml",
        f"{root}/post-sitemap.xml",
        f"{root}/page-sitemap.xml",
        f"{root}/category-sitemap.xml",
        f"{root}/product-category-sitemap.xml",
    ]


def extrair_product_id_url(url: str) -> str:
    path = urlparse(normalizar_url(url)).path.strip("/")
    if not path:
        return ""
    ultimo = path.split("/")[-1]
    full = "/" + path
    padroes = [
        r"(?:produto|product|item|p)[\-/]?(\d{3,})",
        r"(?:id|sku|cod|codigo)[\-/_=]?(\d{3,})",
        r"-(\d{3,})(?:\.html?)?$",
        r"/(\d{3,})(?:\.html?)?$",
    ]
    for padrao in padroes:
        m = re.search(padrao, full, flags=re.I)
        if m:
            return m.group(1)
    m = re.search(r"\b(\d{4,})\b", ultimo)
    if m:
        return m.group(1)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ultimo).strip("-")
    return slug[:80]


def parece_url_produto(url: str) -> bool:
    u = normalizar_url(url).lower()
    if not u:
        return False
    ruins = ["/cart", "/carrinho", "/checkout", "/login", "/account", "/minha-conta", "/blog", "/politica", "/terms", "/termos"]
    if any(r in u for r in ruins):
        return False
    sinais = ["/produto", "/product", "/produtos", "/products", "/p/", "/item", "/catalogo"]
    if any(s in u for s in sinais):
        return True
    return bool(re.search(r"/(?:[^/]+-)?\d{4,}(?:\.html?)?$", urlparse(u).path))


def parece_url_categoria(url: str) -> bool:
    u = normalizar_url(url).lower()
    sinais = ["/categoria", "/category", "/departamento", "/colecao", "/collection", "/loja", "/catalogo"]
    return any(s in u for s in sinais) and not parece_url_produto(u)


def _ignorar_url(url: str) -> bool:
    u = normalizar_url(url).lower()
    ruins = ["/cart", "/carrinho", "/checkout", "/login", "/account", "/minha-conta", "/politica", "/terms", "/termos", "mailto:", "tel:", "javascript:"]
    return any(r in u for r in ruins)


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    urls: list[str] = []
    sitemaps: list[str] = []
    xml_text = _txt(xml_text)
    if not xml_text:
        return urls, sitemaps
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return urls, sitemaps

    for elem in root.iter():
        tag = str(elem.tag).lower()
        if not tag.endswith("loc") or not elem.text:
            continue
        loc = normalizar_url(elem.text)
        if not loc:
            continue
        if loc.lower().endswith(".xml"):
            sitemaps.append(loc)
        else:
            urls.append(loc)
    return urls, sitemaps


def coletar_urls_de_sitemaps(base_url: str, fetcher: Callable[[str], str]) -> tuple[list[str], SitemapCrawlStats]:
    base_url = normalizar_url(base_url)
    stats = SitemapCrawlStats()
    fila = sitemap_candidates(base_url)
    vistos_sitemap = set()
    urls: list[str] = []
    vistos_url = set()

    while fila:
        sm = fila.pop(0)
        if sm in vistos_sitemap or not mesmo_host(base_url, sm):
            continue
        vistos_sitemap.add(sm)
        xml = fetcher(sm)
        if not xml:
            continue
        stats.sitemap_lidos += 1
        page_urls, nested = parse_sitemap(xml)
        for n in nested:
            if n not in vistos_sitemap and mesmo_host(base_url, n):
                fila.append(n)
        for u in page_urls:
            if not mesmo_host(base_url, u) or u in vistos_url or _ignorar_url(u):
                continue
            vistos_url.add(u)
            urls.append(u)

    stats.urls_sitemap = len(urls)
    stats.urls_produto = len([u for u in urls if parece_url_produto(u)])
    stats.motivo = "ok" if urls else "sem_urls_sitemap"
    return urls, stats


def coletar_links_html(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: list[str] = []
    vistos = set()
    for a in soup.find_all("a", href=True):
        url = normalizar_url(urljoin(base_url, _txt(a.get("href"))))
        if not url or url in vistos or not mesmo_host(base_url, url) or _ignorar_url(url):
            continue
        vistos.add(url)
        links.append(url)
    return links


def _json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": lambda v: v and "ld+json" in str(v).lower()}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item.get("@graph"), list):
                    out.extend([x for x in item["@graph"] if isinstance(x, dict)])
                else:
                    out.append(item)
    return out


def _first(*vals: Any) -> str:
    for v in vals:
        if isinstance(v, list):
            v = v[0] if v else ""
        if isinstance(v, dict):
            continue
        t = _txt(v)
        if t:
            return t
    return ""


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _txt(tag.get("content"))
    return ""


def enriquecer_produto_html(url: str, html: str) -> dict[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    data: dict[str, str] = {"url_produto": normalizar_url(url), "produto_id_url": extrair_product_id_url(url)}

    product_obj: dict[str, Any] = {}
    for obj in _json_ld_objects(soup):
        tipo = obj.get("@type", "")
        tipo_txt = " ".join(tipo) if isinstance(tipo, list) else str(tipo)
        if "product" in tipo_txt.lower():
            product_obj = obj
            break

    offers = product_obj.get("offers", {}) if product_obj else {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    brand = product_obj.get("brand", "") if product_obj else ""
    if isinstance(brand, dict):
        brand = brand.get("name", "")

    image = product_obj.get("image", "") if product_obj else ""
    if isinstance(image, list):
        image = "|".join([normalizar_url(urljoin(url, str(x))) for x in image if _txt(x)])

    data["nome"] = _first(product_obj.get("name") if product_obj else "", _meta(soup, "og:title", "twitter:title"), soup.title.string if soup.title else "")
    data["descricao"] = _first(product_obj.get("description") if product_obj else "", _meta(soup, "og:description", "description", "twitter:description"))
    data["marca"] = _first(brand)
    data["preco"] = _first(offers.get("price") if isinstance(offers, dict) else "", _meta(soup, "product:price:amount", "og:price:amount"))
    data["moeda"] = _first(offers.get("priceCurrency") if isinstance(offers, dict) else "", _meta(soup, "product:price:currency"))
    data["gtin"] = _first(product_obj.get("gtin13") if product_obj else "", product_obj.get("gtin") if product_obj else "", product_obj.get("gtin14") if product_obj else "")
    data["sku"] = _first(product_obj.get("sku") if product_obj else "", data.get("produto_id_url", ""))
    data["imagens"] = _first(image, _meta(soup, "og:image", "twitter:image"))
    data["categoria"] = _first(product_obj.get("category") if product_obj else "")

    if not data.get("preco"):
        text = soup.get_text(" ", strip=True)
        m = re.search(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+[\.,]\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}", text)
        if m:
            data["preco"] = m.group(0)

    return {k: v for k, v in data.items() if _txt(v)}


def _ordenar_df(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows).fillna("")
    if df.empty:
        return df
    ordem = ["produto_id_url", "sku", "nome", "preco", "moeda", "marca", "categoria", "gtin", "estoque", "url_produto", "imagens", "descricao"]
    for col in ordem:
        if col not in df.columns:
            df[col] = ""
    df = df[ordem + [c for c in df.columns if c not in ordem]]
    if "url_produto" in df.columns:
        df = df.drop_duplicates(subset=["url_produto"], keep="first")
    return df.reset_index(drop=True)


def varrer_site_por_sitemap(base_url: str, fetcher: Callable[[str], str], limite_produtos: int | None = None) -> tuple[pd.DataFrame, SitemapCrawlStats]:
    base_url = normalizar_url(base_url)
    urls, stats = coletar_urls_de_sitemaps(base_url, fetcher)

    fila = []
    vistos_fila = set()
    for u in [base_url] + urls:
        if u and u not in vistos_fila:
            fila.append(u)
            vistos_fila.add(u)

    rows: list[dict[str, str]] = []
    visitadas = set()
    produtos_vistos = set()
    ciclos_sem_novidade = 0

    while fila:
        u = fila.pop(0)
        if u in visitadas or not mesmo_host(base_url, u) or _ignorar_url(u):
            continue
        visitadas.add(u)
        html = fetcher(u)
        stats.paginas_processadas += 1
        if not html:
            ciclos_sem_novidade += 1
            continue

        novos_antes = len(fila) + len(rows)

        if parece_url_produto(u):
            row = enriquecer_produto_html(u, html)
            key = row.get("produto_id_url") or row.get("url_produto") or u
            if key and key not in produtos_vistos and (row.get("nome") or row.get("preco") or row.get("produto_id_url")):
                produtos_vistos.add(key)
                rows.append(row)

        if parece_url_categoria(u) or u == base_url or not parece_url_produto(u):
            stats.categorias_processadas += 1
            for link in coletar_links_html(base_url, html):
                if link not in visitadas and link not in vistos_fila:
                    fila.append(link)
                    vistos_fila.add(link)

        novos_depois = len(fila) + len(rows)
        ciclos_sem_novidade = ciclos_sem_novidade + 1 if novos_depois <= novos_antes else 0
        if ciclos_sem_novidade >= 250 and not fila:
            break

    stats.urls_visitadas = len(visitadas)
    stats.urls_produto = len([u for u in visitadas if parece_url_produto(u)])
    stats.produtos_extraidos = len(rows)
    stats.motivo = "sem_novas_urls" if rows else "sem_produtos_extraidos"
    return _ordenar_df(rows), stats
