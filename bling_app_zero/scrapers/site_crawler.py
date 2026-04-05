import posixpath
import re
import xml.etree.ElementTree as ET
from collections import deque
from typing import Dict, List, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

try:
    from .ai_enriquecimento import enriquecer_produto_com_ia
except ModuleNotFoundError:
    def enriquecer_produto_com_ia(dados, html="", url=""):
        return dados

from .extrator_produto import classificar_pagina, extrair_produto_html
from .fetcher import baixar_html


IGNORED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
)

PRODUCT_HINTS = (
    "/produto",
    "/product",
    "/p/",
    "/pd-",
    "/item/",
    "/sku/",
    "/shop/",
)

CATEGORY_HINTS = (
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

MEGA_CENTER_HOSTS = {
    "megacentereletronicos.com.br",
    "www.megacentereletronicos.com.br",
}

MEGA_CENTER_SEED_PATHS = (
    "/produtos",
    "/produtos?pagina=1",
    "/produtos?page=1",
    "/produtos?p=1",
    "/",
)


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _canonicalizar_url(url: str) -> str:
    url = _normalizar_url(url)
    if not url:
        return ""

    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    path = parsed.path or "/"
    path = re.sub(r"/+", "/", path)
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        kk = (k or "").strip().lower()
        vv = (v or "").strip()
        if kk in {"pagina", "page", "p", "offset"} and vv:
            query_items.append((kk, vv))
    query = urlencode(query_items)

    return urlunparse((scheme, netloc, path, "", query, ""))


def _mesmo_dominio(url: str, dominio_base: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return host == dominio_base or host.endswith("." + dominio_base)


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _eh_mega_center(url: str) -> bool:
    return _host(url) in MEGA_CENTER_HOSTS


def _url_ignorada(url: str) -> bool:
    baixa = url.lower()
    return (
        any(ext in baixa for ext in IGNORED_EXTENSIONS)
        or "mailto:" in baixa
        or "tel:" in baixa
        or "whatsapp" in baixa
        or "/cart" in baixa
        or "/checkout" in baixa
        or "/login" in baixa
        or "/account" in baixa
        or "/carrinho" in baixa
        or "/pedido" in baixa
        or "/rastrear" in baixa
    )


def _score_link(url: str, dominio_base: str) -> int:
    baixa = url.lower()
    score = 0

    if any(token in baixa for token in PRODUCT_HINTS):
        score += 5
    if any(token in baixa for token in CATEGORY_HINTS):
        score += 3

    if re.search(r"/[a-z0-9\-_]+/p$", baixa):
        score += 4

    if "pagina=" in baixa or "page=" in baixa or "/page/" in baixa:
        score += 2

    if "/produtos" in baixa:
        score += 6

    if dominio_base in MEGA_CENTER_HOSTS:
        if "/produtos" in baixa:
            score += 12
        if "pagina=" in baixa or "page=" in baixa or "p=" in baixa:
            score += 8
        if baixa.count("/") >= 4 and "/produtos" not in baixa:
            score += 2

    score += baixa.count("/")
    return score


def _limpar_texto(txt: str) -> str:
    return " ".join((txt or "").split()).strip()


def _slugifica(txt: str) -> str:
    txt = _limpar_texto(txt).lower()
    txt = re.sub(r"[^\w\s-]", "", txt, flags=re.UNICODE)
    txt = re.sub(r"[\s_]+", "-", txt)
    txt = re.sub(r"-{2,}", "-", txt)
    return txt.strip("-")


def _extrair_links(html: str, base_url: str, dominio_base: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: List[str] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        absoluto = _canonicalizar_url(urljoin(base_url, href))
        if not absoluto:
            continue
        if not _mesmo_dominio(absoluto, dominio_base):
            continue
        if _url_ignorada(absoluto):
            continue

        links.append(absoluto)

    unicos = sorted(set(links), key=lambda x: (-_score_link(x, dominio_base), x))
    return unicos


def _descobrir_sitemaps(url_base: str, html_home: str) -> List[str]:
    candidatos = [
        urljoin(url_base, "/sitemap.xml"),
        urljoin(url_base, "/sitemap_index.xml"),
    ]

    soup = BeautifulSoup(html_home or "", "html.parser")
    for link in soup.find_all("link", attrs={"rel": re.compile("sitemap", re.I)}):
        href = link.get("href")
        if href:
            candidatos.append(urljoin(url_base, href))

    vistos: List[str] = []
    for item in candidatos:
        canon = _canonicalizar_url(item)
        if canon and canon not in vistos:
            vistos.append(canon)
    return vistos


def _parse_sitemap_urls(xml_texto: str, limite: int = 1000) -> List[str]:
    if not xml_texto:
        return []

    try:
        root = ET.fromstring(xml_texto)
    except Exception:
        return []

    urls: List[str] = []
    for elem in root.iter():
        tag = elem.tag.split("}", 1)[-1].lower()
        if tag == "loc" and elem.text:
            urls.append(elem.text.strip())
            if len(urls) >= limite:
                break
    return urls


def _carregar_urls_do_sitemap(
    url_base: str,
    html_home: str,
    dominio_base: str,
    limite_total: int = 1500,
) -> List[str]:
    urls: List[str] = []
    fila = deque(_descobrir_sitemaps(url_base, html_home))
    vistos: Set[str] = set()

    while fila and len(urls) < limite_total:
        sitemap_url = fila.popleft()
        if sitemap_url in vistos:
            continue
        vistos.add(sitemap_url)

        resp = baixar_html(sitemap_url, timeout=25)
        if not resp.get("ok"):
            continue

        bruto = _parse_sitemap_urls(resp.get("html", ""), limite=limite_total)
        for item in bruto:
            canon = _canonicalizar_url(item)
            if not canon:
                continue

            if canon.endswith(".xml"):
                if canon not in vistos:
                    fila.append(canon)
                continue

            if _mesmo_dominio(canon, dominio_base) and not _url_ignorada(canon):
                urls.append(canon)
                if len(urls) >= limite_total:
                    break

    return list(dict.fromkeys(urls))


def _gerar_paginas_produtos(url_base: str, max_paginas: int = 30) -> List[str]:
    base = _canonicalizar_url(urljoin(url_base, "/produtos"))
    urls = [base]

    for pagina in range(1, max_paginas + 1):
        urls.append(_canonicalizar_url(f"{base}?pagina={pagina}"))
        urls.append(_canonicalizar_url(f"{base}?page={pagina}"))
        urls.append(_canonicalizar_url(f"{base}?p={pagina}"))
        urls.append(_canonicalizar_url(urljoin(url_base, f"/produtos/pagina/{pagina}")))
        urls.append(_canonicalizar_url(urljoin(url_base, f"/produtos/page/{pagina}")))

    return list(dict.fromkeys([u for u in urls if u]))


def _extrair_breadcrumbs(soup: BeautifulSoup) -> str:
    crumbs: List[str] = []

    seletores = [
        "[aria-label='breadcrumb'] a",
        ".breadcrumb a",
        ".breadcrumbs a",
        "nav.breadcrumb a",
        "ol.breadcrumb li",
        "ul.breadcrumb li",
    ]

    for seletor in seletores:
        for tag in soup.select(seletor):
            txt = _limpar_texto(tag.get_text(" ", strip=True))
            if txt and txt.lower() not in {"home", "início", "inicio"}:
                crumbs.append(txt)

    unicos = list(dict.fromkeys(crumbs))
    return " > ".join(unicos[-4:])


def _extrair_links_json_embutido(html: str, base_url: str, dominio_base: str) -> List[str]:
    if not html:
        return []

    candidatos: List[str] = []

    for match in re.findall(r'https?://[^"\']+', html, flags=re.I):
        candidatos.append(match)

    for match in re.findall(r'/(?:produtos?|produto|p)/[^"\']+', html, flags=re.I):
        candidatos.append(urljoin(base_url, match))

    saida: List[str] = []
    for item in candidatos:
        canon = _canonicalizar_url(item)
        if not canon:
            continue
        if not _mesmo_dominio(canon, dominio_base):
            continue
        if _url_ignorada(canon):
            continue
        saida.append(canon)

    return list(dict.fromkeys(saida))


def _enriquecer_contexto_categoria(extraido: Dict, html: str, url_final: str) -> Dict:
    extraido = dict(extraido or {})
    soup = BeautifulSoup(html or "", "html.parser")

    breadcrumbs = _extrair_breadcrumbs(soup)
    if breadcrumbs and not extraido.get("categoria"):
        extraido["categoria"] = breadcrumbs

    if not extraido.get("origem_arquivo_ou_url"):
        extraido["origem_arquivo_ou_url"] = url_final

    return extraido


def _montar_sementes(url_base: str, html_home: str, dominio_base: str) -> List[str]:
    sementes: List[str] = [url_base]

    if dominio_base in MEGA_CENTER_HOSTS:
        sementes.extend(_gerar_paginas_produtos(url_base, max_paginas=40))
        sementes.extend(_extrair_links_json_embutido(html_home, url_base, dominio_base))
    else:
        sementes.extend(_carregar_urls_do_sitemap(url_base, html_home, dominio_base, limite_total=1500))
        sementes.extend(_extrair_links(html_home, url_base, dominio_base))

    unicas: List[str] = []
    vistos: Set[str] = set()
    for item in sementes:
        canon = _canonicalizar_url(item)
        if canon and canon not in vistos:
            vistos.add(canon)
            unicas.append(canon)

    return sorted(unicas, key=lambda x: (-_score_link(x, dominio_base), x))


def _mega_center_pode_ser_listagem(url: str, html: str) -> bool:
    baixa = (url or "").lower()
    texto = _limpar_texto(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)).lower()

    return (
        "/produtos" in baixa
        or "carregar mais produtos" in texto
        or "todos produtos" in texto
        or "ordenar por:" in texto
    )


def extrair_produtos_de_site(
    url_inicial: str,
    limite_paginas: int = 220,
    limite_produtos: int = 1000,
) -> pd.DataFrame:
    url_inicial = _canonicalizar_url(url_inicial)
    if not url_inicial:
        raise ValueError("Informe uma URL válida do site da loja.")

    home = baixar_html(url_inicial, timeout=25)
    if not home.get("ok"):
        raise ValueError(f"Não foi possível acessar o site informado: {home.get('erro', 'falha desconhecida')}")

    url_base = home.get("url", url_inicial)
    url_base = _canonicalizar_url(url_base)
    dominio_base = (urlparse(url_base).netloc or "").lower()
    html_home = home.get("html", "")

    fila = deque()
    visitados: Set[str] = set()
    produtos_visitados: Set[str] = set()

    sementes = _montar_sementes(url_base, html_home, dominio_base)
    for item in sementes:
        fila.append(item)

    linhas: List[Dict] = []
    paginas_processadas = 0

    while fila and paginas_processadas < limite_paginas and len(linhas) < limite_produtos:
        atual = fila.popleft()
        atual = _canonicalizar_url(atual)

        if not atual or atual in visitados:
            continue

        visitados.add(atual)
        resp = home if atual == _canonicalizar_url(url_base) else baixar_html(atual, timeout=20)
        paginas_processadas += 1

        if not resp.get("ok"):
            continue

        url_final = _canonicalizar_url(resp.get("url", atual))
        html = resp.get("html", "")
        if not html:
            continue

        classificacao = classificar_pagina(html, url_final)
        eh_produto = bool(classificacao.get("is_product"))
        eh_listagem_mega = dominio_base in MEGA_CENTER_HOSTS and _mega_center_pode_ser_listagem(url_final, html)

        if eh_produto and url_final not in produtos_visitados:
            extraido = extrair_produto_html(html, url_final)
            extraido = _enriquecer_contexto_categoria(extraido, html, url_final)
            extraido = enriquecer_produto_com_ia(extraido, html, url_final)

            if extraido.get("nome") or extraido.get("descricao") or extraido.get("descricao_curta"):
                produtos_visitados.add(url_final)
                extraido["erro_scraper"] = ""
                linhas.append(extraido)

                if len(linhas) >= limite_produtos:
                    break

        links_html = _extrair_links(html, url_final, dominio_base)
        links_json = _extrair_links_json_embutido(html, url_final, dominio_base)
        links = list(dict.fromkeys(links_html + links_json))

        for link in links:
            if link in visitados:
                continue

            baixa = link.lower()

            if dominio_base in MEGA_CENTER_HOSTS:
                if "/produtos" in baixa:
                    fila.appendleft(link)
                    continue
                if "pagina=" in baixa or "page=" in baixa or "p=" in baixa:
                    fila.appendleft(link)
                    continue
                if any(token in baixa for token in PRODUCT_HINTS):
                    fila.appendleft(link)
                    continue
                fila.append(link)
                continue

            if any(token in baixa for token in PRODUCT_HINTS + CATEGORY_HINTS):
                fila.appendleft(link)
            else:
                fila.append(link)

        if dominio_base in MEGA_CENTER_HOSTS and eh_listagem_mega:
            for pagina in range(1, 41):
                for seed in (
                    f"{url_base.rstrip('/')}/produtos?pagina={pagina}",
                    f"{url_base.rstrip('/')}/produtos?page={pagina}",
                    f"{url_base.rstrip('/')}/produtos?p={pagina}",
                ):
                    canon = _canonicalizar_url(seed)
                    if canon and canon not in visitados:
                        fila.append(canon)

    if not linhas:
        raise ValueError("Nenhum produto foi encontrado automaticamente no site informado.")

    df = pd.DataFrame(linhas)

    if "origem_arquivo_ou_url" in df.columns:
        df = df.drop_duplicates(subset=["origem_arquivo_ou_url"]).reset_index(drop=True)
    else:
        df = df.drop_duplicates().reset_index(drop=True)

    return df
