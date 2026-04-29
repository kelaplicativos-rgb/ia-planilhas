"""
CRAWLER ENGINE — UNIVERSAL DATA SCRAPER MODE

Objetivo:
- Trabalhar no estilo Instant Data Scraper:
  1. Ler o HTML da página.
  2. Detectar blocos repetidos automaticamente.
  3. Extrair tabela/listagem/card sem depender de regra fixa por site.
  4. Continuar compatível com o fluxo atual do Bling.
- Mantém fallback antigo:
  sitemap + links de produto + extração heurística individual.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from bling_app_zero.core.site_crawler_cleaners import (
    normalizar_texto,
    normalizar_url,
    safe_str,
)
from bling_app_zero.core.site_crawler_http import (
    extrair_detalhes_heuristicos,
    fetch_html_retry,
    normalizar_link_crawl,
    url_valida_para_crawl,
)
from bling_app_zero.core.site_crawler_links import (
    descobrir_produtos_no_dominio,
    extrair_links_pagina,
)


HEADERS_POOL = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
]

PRODUCT_HINTS = (
    "/produto",
    "/produtos",
    "/product",
    "/products",
    "/p/",
    "/item",
    "/sku",
    "/prd",
)

BAD_LINK_HINTS = (
    "/login",
    "/logout",
    "/account",
    "/conta",
    "/cart",
    "/carrinho",
    "/checkout",
    "/politica",
    "/privacy",
    "/termos",
    "/terms",
    "mailto:",
    "tel:",
    "whatsapp",
    "javascript:",
)

SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/product-sitemap.xml",
    "/produto-sitemap.xml",
    "/products-sitemap.xml",
    "/sitemap_products.xml",
    "/sitemap-produtos.xml",
)

OUTPUT_COLUMNS = [
    "url_produto",
    "nome",
    "sku",
    "marca",
    "categoria",
    "estoque",
    "preco",
    "gtin",
    "descricao",
    "imagens",
]

CARD_SELECTORS = [
    "li",
    "article",
    "div",
    "section",
    "tr",
]

PRICE_RE = re.compile(
    r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+,\d{2}",
    flags=re.I,
)

GTIN_RE = re.compile(r"\b\d{8}\b|\b\d{12}\b|\b\d{13}\b|\b\d{14}\b")

SKU_RE = re.compile(
    r"(?:sku|c[oó]digo|cod\.?|ref\.?|refer[eê]ncia|modelo)\s*[:#-]?\s*([A-Z0-9._/-]{3,40})",
    flags=re.I,
)


@dataclass
class CandidateBlock:
    selector_signature: str
    score: float
    rows: list[dict[str, Any]]


def _log(msg: str) -> None:
    texto = safe_str(msg)
    if not texto:
        return

    try:
        if st is not None:
            logs = st.session_state.setdefault("logs", [])
            logs.append(texto)
    except Exception:
        pass

    try:
        print(texto)
    except Exception:
        pass


def _raiz(url: str) -> str:
    parsed = urlparse(normalizar_url(url))
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return normalizar_url(url)


def _host(url: str) -> str:
    try:
        return urlparse(normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_host(base_url: str, url: str) -> bool:
    return _host(base_url) == _host(url)


def _url_ruim(url: str) -> bool:
    url_n = normalizar_texto(url)
    return any(x in url_n for x in BAD_LINK_HINTS)


def _parece_produto_url(url: str) -> bool:
    url_n = normalizar_texto(url)
    if not url_n or _url_ruim(url_n):
        return False

    if any(h in url_n for h in PRODUCT_HINTS):
        return True

    path = urlparse(normalizar_url(url)).path.strip("/")
    partes = [p for p in path.split("/") if p]

    if len(partes) >= 2:
        ultimo = partes[-1]
        if "-" in ultimo and len(ultimo) >= 10:
            return True

    return False


def _parece_categoria_url(url: str) -> bool:
    url_n = normalizar_texto(url)
    sinais = (
        "/categoria",
        "/categorias",
        "/departamento",
        "/departamentos",
        "/collection",
        "/collections",
        "/busca",
        "/search",
        "page=",
        "pagina=",
        "/page/",
    )
    return any(s in url_n for s in sinais)


def _html_tem_produto(html: str) -> bool:
    html_n = normalizar_texto(html)
    sinais = (
        '"@type":"product"',
        '"@type": "product"',
        "application/ld+json",
        "product:price",
        "itemprop='price'",
        'itemprop="price"',
        "adicionar ao carrinho",
        "comprar agora",
        "add to cart",
        "sku",
        "gtin",
        "ean",
        "r$",
    )
    return any(s in html_n for s in sinais)


def _criar_session(auth_context: dict[str, Any] | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS_POOL[0])

    if not isinstance(auth_context, dict):
        return session

    headers = auth_context.get("headers")
    if isinstance(headers, dict):
        for k, v in headers.items():
            k_s = safe_str(k)
            v_s = safe_str(v)
            if k_s and v_s:
                session.headers[k_s] = v_s

    cookies = auth_context.get("cookies")
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue

            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"

            if not nome:
                continue

            try:
                session.cookies.set(nome, valor, domain=dominio or None, path=path)
            except Exception:
                continue

    return session


def _fetch(session: requests.Session, url: str, timeout: int = 35) -> str:
    url = normalizar_url(url)
    if not url:
        return ""

    try:
        html = fetch_html_retry(url, timeout=timeout, tentativas=2)
        if safe_str(html):
            return safe_str(html)
    except Exception:
        pass

    for headers in HEADERS_POOL:
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=True,
            )
            if response.ok and safe_str(response.text):
                return response.text
        except Exception:
            pass

        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=False,
            )
            if response.ok and safe_str(response.text):
                return response.text
        except Exception:
            pass

    return ""


def _limpar_preco(valor: str) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""

    match = PRICE_RE.search(texto)
    if not match:
        return ""

    preco = match.group(0)
    preco = preco.replace("R$", "").replace("\xa0", " ").strip()
    return preco


def _limpar_gtin(valor: str) -> str:
    digitos = re.sub(r"\D+", "", safe_str(valor))
    if len(digitos) in (8, 12, 13, 14):
        return digitos
    return ""


def _dedupe_lista(valores: list[str], limite: int = 12) -> list[str]:
    saida = []
    vistos = set()

    for valor in valores:
        v = safe_str(valor).strip()
        if not v:
            continue

        chave = v.lower()
        if chave in vistos:
            continue

        vistos.add(chave)
        saida.append(v)

        if len(saida) >= limite:
            break

    return saida


def _imagem_valida(src: str) -> bool:
    src_n = normalizar_texto(src)

    if not src_n:
        return False

    ruins = (
        "logo",
        "sprite",
        "placeholder",
        "loading",
        "blank",
        "icone",
        "icon",
        "whatsapp",
        "facebook",
        "instagram",
        "youtube",
        "banner",
        "tracking",
        "pixel",
    )

    if any(r in src_n for r in ruins):
        return False

    boas = (".jpg", ".jpeg", ".png", ".webp", "/image/", "/images/", "/img/")
    return any(b in src_n for b in boas)


def _element_text(el: Tag) -> str:
    texto = el.get_text(" ", strip=True)
    texto = re.sub(r"\s+", " ", safe_str(texto)).strip()
    return texto


def _signature(el: Tag) -> str:
    classes = el.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()

    classes_limpas = []
    for c in classes:
        c = safe_str(c).strip().lower()
        if not c:
            continue
        if re.search(r"\d{3,}", c):
            continue
        classes_limpas.append(c)

    classes_limpas = sorted(classes_limpas[:5])
    return f"{el.name}|{'.'.join(classes_limpas)}"


def _extrair_nome_do_bloco(el: Tag) -> str:
    candidatos = []

    for seletor in [
        "h1",
        "h2",
        "h3",
        "h4",
        "[itemprop='name']",
        ".name",
        ".nome",
        ".title",
        ".titulo",
        ".product-name",
        ".product-title",
        ".card-title",
    ]:
        found = el.select_one(seletor)
        if found:
            candidatos.append(_element_text(found))

    for attr in ["title", "aria-label", "alt"]:
        valor = safe_str(el.get(attr))
        if valor:
            candidatos.append(valor)

    for a in el.find_all("a", href=True):
        texto = _element_text(a)
        if texto and len(texto) >= 4:
            candidatos.append(texto)

    candidatos = _dedupe_lista(candidatos, limite=10)
    candidatos = sorted(candidatos, key=lambda x: (len(x) < 4, len(x) > 160, -len(x)))

    for c in candidatos:
        c = safe_str(c)
        if len(c) >= 4 and not PRICE_RE.fullmatch(c):
            return c[:220]

    return ""


def _extrair_url_do_bloco(base_url: str, el: Tag) -> str:
    links = []

    for a in el.find_all("a", href=True):
        href = normalizar_link_crawl(base_url, safe_str(a.get("href")))
        if not href:
            continue
        if _url_ruim(href):
            continue
        links.append(href)

    links = _dedupe_lista(links, limite=12)

    for link in links:
        if _parece_produto_url(link):
            return link

    return links[0] if links else ""


def _extrair_imagens_do_bloco(base_url: str, el: Tag) -> str:
    imagens = []

    for img in el.find_all("img"):
        for attr in ["src", "data-src", "data-original", "data-lazy", "data-lazy-src", "srcset"]:
            raw = safe_str(img.get(attr))
            if not raw:
                continue

            if attr == "srcset":
                partes = [p.strip().split(" ")[0] for p in raw.split(",")]
            else:
                partes = [raw]

            for parte in partes:
                url_img = urljoin(base_url, parte)
                if _imagem_valida(url_img):
                    imagens.append(url_img)

    imagens = _dedupe_lista(imagens, limite=12)
    return "|".join(imagens)


def _extrair_sku_do_texto(texto: str) -> str:
    texto = safe_str(texto)
    match = SKU_RE.search(texto)
    if match:
        return safe_str(match.group(1))[:60]

    return ""


def _extrair_estoque_do_texto(texto: str) -> str:
    texto_n = normalizar_texto(texto)

    sem_estoque = (
        "sem estoque",
        "indisponivel",
        "indisponível",
        "esgotado",
        "produto indisponivel",
        "produto indisponível",
    )

    if any(s in texto_n for s in sem_estoque):
        return "0"

    match = re.search(r"(?:estoque|dispon[ií]vel|quantidade|qtd)\s*[:#-]?\s*(\d+)", texto, flags=re.I)
    if match:
        return safe_str(match.group(1))

    if any(s in texto_n for s in ("comprar", "adicionar ao carrinho", "em estoque", "disponivel", "disponível")):
        return "1"

    return ""


def _linha_do_bloco(base_url: str, el: Tag) -> dict[str, Any]:
    texto = _element_text(el)

    nome = _extrair_nome_do_bloco(el)
    url_produto = _extrair_url_do_bloco(base_url, el)
    imagens = _extrair_imagens_do_bloco(base_url, el)
    preco = _limpar_preco(texto)
    gtin_match = GTIN_RE.search(texto)
    gtin = _limpar_gtin(gtin_match.group(0) if gtin_match else "")
    sku = _extrair_sku_do_texto(texto)
    estoque = _extrair_estoque_do_texto(texto)

    return {
        "url_produto": url_produto,
        "nome": nome,
        "sku": sku,
        "marca": "",
        "categoria": "",
        "estoque": estoque or "1",
        "preco": preco,
        "gtin": gtin,
        "descricao": texto[:1000],
        "imagens": imagens,
    }


def _score_linha(row: dict[str, Any]) -> float:
    score = 0.0

    if safe_str(row.get("nome")):
        score += 4

    if safe_str(row.get("preco")):
        score += 3

    if safe_str(row.get("url_produto")):
        score += 2

    if safe_str(row.get("imagens")):
        score += 1.5

    if safe_str(row.get("sku")):
        score += 1

    if safe_str(row.get("gtin")):
        score += 1

    descricao = safe_str(row.get("descricao"))

    if len(descricao) < 15:
        score -= 3

    if len(descricao) > 2500:
        score -= 2

    return score


def _linha_valida_universal(row: dict[str, Any]) -> bool:
    nome = safe_str(row.get("nome"))
    preco = safe_str(row.get("preco"))
    url_produto = safe_str(row.get("url_produto"))
    imagens = safe_str(row.get("imagens"))
    descricao = safe_str(row.get("descricao"))

    if not nome and not url_produto:
        return False

    if len(descricao) < 10:
        return False

    pontos = 0
    if nome:
        pontos += 2
    if preco:
        pontos += 2
    if url_produto:
        pontos += 1
    if imagens:
        pontos += 1

    return pontos >= 3


def _detectar_blocos_repetidos(base_url: str, html: str, limite: int = 800) -> pd.DataFrame:
    """
    Tecnologia principal estilo Instant Data Scraper:
    procura grupos de elementos parecidos e transforma o melhor grupo em tabela.
    """

    html = safe_str(html)
    if not html:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    elementos = []
    for seletor in CARD_SELECTORS:
        elementos.extend(soup.find_all(seletor))

    grupos: dict[str, list[Tag]] = {}

    for el in elementos:
        if not isinstance(el, Tag):
            continue

        texto = _element_text(el)
        if len(texto) < 20:
            continue

        if len(texto) > 4000:
            continue

        sig = _signature(el)
        grupos.setdefault(sig, []).append(el)

    candidatos: list[CandidateBlock] = []

    for sig, els in grupos.items():
        if len(els) < 2:
            continue

        rows = []
        vistos = set()

        for el in els[:limite]:
            row = _linha_do_bloco(base_url, el)

            if not _linha_valida_universal(row):
                continue

            chave = (
                safe_str(row.get("url_produto")).lower(),
                safe_str(row.get("sku")).lower(),
                safe_str(row.get("nome")).lower(),
                safe_str(row.get("preco")).lower(),
            )

            if chave in vistos:
                continue

            vistos.add(chave)
            rows.append(row)

        if len(rows) < 2:
            continue

        media_score = sum(_score_linha(r) for r in rows) / max(len(rows), 1)

        diversidade_nome = len({safe_str(r.get("nome")).lower() for r in rows if safe_str(r.get("nome"))})
        diversidade_url = len({safe_str(r.get("url_produto")).lower() for r in rows if safe_str(r.get("url_produto"))})

        score = media_score
        score += min(len(rows), 50) * 0.25
        score += min(diversidade_nome, 50) * 0.15
        score += min(diversidade_url, 50) * 0.15

        candidatos.append(CandidateBlock(selector_signature=sig, score=score, rows=rows))

    if not candidatos:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    candidatos.sort(key=lambda c: c.score, reverse=True)
    melhor = candidatos[0]

    _log(
        "[UNIVERSAL_SCRAPER] Melhor estrutura detectada "
        f"| assinatura={melhor.selector_signature} "
        f"| linhas={len(melhor.rows)} "
        f"| score={melhor.score:.2f}"
    )

    return _normalizar_saida(melhor.rows)


def _extrair_jsonld_produtos(base_url: str, html: str) -> pd.DataFrame:
    soup = BeautifulSoup(safe_str(html), "lxml")
    produtos: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return

        if not isinstance(obj, dict):
            return

        tipo = obj.get("@type") or obj.get("type")
        tipos = tipo if isinstance(tipo, list) else [tipo]
        tipos_n = [normalizar_texto(str(t)) for t in tipos]

        if "product" in tipos_n:
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            imagens = obj.get("image") or []
            if isinstance(imagens, str):
                imagens = [imagens]

            produto = {
                "url_produto": normalizar_link_crawl(base_url, safe_str(obj.get("url") or base_url)),
                "nome": safe_str(obj.get("name")),
                "sku": safe_str(obj.get("sku") or obj.get("mpn")),
                "marca": safe_str(
                    obj.get("brand", {}).get("name")
                    if isinstance(obj.get("brand"), dict)
                    else obj.get("brand")
                ),
                "categoria": safe_str(obj.get("category")),
                "estoque": "0" if "outofstock" in normalizar_texto(str(offers.get("availability"))) else "1",
                "preco": safe_str(offers.get("price") or offers.get("lowPrice") or ""),
                "gtin": _limpar_gtin(
                    safe_str(
                        obj.get("gtin")
                        or obj.get("gtin8")
                        or obj.get("gtin12")
                        or obj.get("gtin13")
                        or obj.get("gtin14")
                    )
                ),
                "descricao": safe_str(obj.get("description") or obj.get("name")),
                "imagens": "|".join(
                    _dedupe_lista([urljoin(base_url, safe_str(img)) for img in imagens if safe_str(img)], limite=12)
                ),
            }
            produtos.append(produto)

        for value in obj.values():
            if isinstance(value, (list, dict)):
                walk(value)

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = safe_str(script.string or script.get_text(" ", strip=True))
        if not raw:
            continue

        try:
            data = json.loads(raw)
            walk(data)
        except Exception:
            continue

    return _normalizar_saida(produtos)


def _descobrir_proximas_paginas(base_url: str, html: str, limite: int = 10) -> list[str]:
    soup = BeautifulSoup(safe_str(html), "lxml")
    links: list[str] = []

    palavras = (
        "proxima",
        "próxima",
        "seguinte",
        "next",
        "mais",
        "ver mais",
        "carregar mais",
    )

    for a in soup.find_all("a", href=True):
        texto = normalizar_texto(a.get_text(" ", strip=True))
        aria = normalizar_texto(safe_str(a.get("aria-label")))
        rel = normalizar_texto(" ".join(a.get("rel") or []))
        href = normalizar_link_crawl(base_url, safe_str(a.get("href")))

        if not href or _url_ruim(href):
            continue

        contexto = f"{texto} {aria} {rel} {href}".lower()

        if any(p in contexto for p in palavras) or "page=" in contexto or "pagina=" in contexto:
            if href not in links:
                links.append(href)

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query))

    for key in ["page", "pagina", "p"]:
        atual = query.get(key)
        if atual and atual.isdigit():
            for n in range(int(atual) + 1, int(atual) + 4):
                query2 = query.copy()
                query2[key] = str(n)
                nova_query = urlencode(query2)
                nova_url = urlunparse(parsed._replace(query=nova_query))
                if nova_url not in links:
                    links.append(nova_url)

    return links[:limite]


def _universal_scrape_paginas(
    session: requests.Session,
    base_url: str,
    *,
    limite_paginas: int,
    limite_produtos: int,
    max_segundos: int,
) -> pd.DataFrame:
    inicio = time.time()
    fila = deque([base_url])
    visitadas: set[str] = set()
    linhas: list[dict[str, Any]] = []

    while fila:
        if len(visitadas) >= limite_paginas:
            break

        if len(linhas) >= limite_produtos:
            break

        if time.time() - inicio > max_segundos:
            break

        url_atual = fila.popleft()

        if url_atual in visitadas:
            continue

        visitadas.add(url_atual)

        html = _fetch(session, url_atual)
        if not html:
            continue

        df_jsonld = _extrair_jsonld_produtos(url_atual, html)
        df_dom = _detectar_blocos_repetidos(url_atual, html, limite=limite_produtos)

        for df in [df_jsonld, df_dom]:
            if df.empty:
                continue

            for item in df.to_dict("records"):
                linhas.append(item)

                if len(linhas) >= limite_produtos:
                    break

        proximas = _descobrir_proximas_paginas(url_atual, html, limite=8)

        for prox in proximas:
            if prox in visitadas or prox in fila:
                continue

            if not _mesmo_host(base_url, prox):
                continue

            fila.append(prox)

        _log(
            "[UNIVERSAL_SCRAPER] Página analisada "
            f"| {len(visitadas)}/{limite_paginas} "
            f"| linhas={len(linhas)} "
            f"| url={url_atual}"
        )

    return _normalizar_saida(linhas)


def _extrair_urls_de_sitemap_xml(base_url: str, xml_text: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    xml_text = safe_str(xml_text)
    if not xml_text:
        return urls

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
        for loc in root.iter():
            tag = safe_str(loc.tag).lower()
            if not tag.endswith("loc"):
                continue

            valor = normalizar_link_crawl(base_url, safe_str(loc.text))

            if not valor or valor in vistos:
                continue

            if not url_valida_para_crawl(base_url, valor):
                continue

            vistos.add(valor)
            urls.append(valor)

    except Exception:
        for match in re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml_text, flags=re.I):
            valor = normalizar_link_crawl(base_url, match)

            if valor and valor not in vistos and url_valida_para_crawl(base_url, valor):
                vistos.add(valor)
                urls.append(valor)

    return urls


def _buscar_sitemaps(session: requests.Session, base_url: str, max_sitemaps: int = 30) -> list[str]:
    raiz = _raiz(base_url)
    candidatos = [f"{raiz}{path}" for path in SITEMAP_PATHS]
    fila = deque(candidatos)
    visitados: set[str] = set()
    urls: list[str] = []
    vistos_urls: set[str] = set()

    while fila and len(visitados) < max_sitemaps:
        sitemap_url = fila.popleft()

        if sitemap_url in visitados:
            continue

        visitados.add(sitemap_url)
        xml_text = _fetch(session, sitemap_url, timeout=25)

        if not xml_text:
            continue

        encontrados = _extrair_urls_de_sitemap_xml(base_url, xml_text)

        for item in encontrados:
            item_n = normalizar_texto(item)

            if (item_n.endswith(".xml") or "sitemap" in item_n) and item_n not in visitados:
                fila.append(item)
                continue

            if item not in vistos_urls:
                vistos_urls.add(item)
                urls.append(item)

    return urls


def _extrair_links_js(base_url: str, html: str) -> list[str]:
    html = safe_str(html)
    if not html:
        return []

    padroes = [
        r"https?://[^\"'<>\\\s]+",
        r"\/produto\/[^\"'<>\\\s]+",
        r"\/produtos\/[^\"'<>\\\s]+",
        r"\/product\/[^\"'<>\\\s]+",
        r"\/products\/[^\"'<>\\\s]+",
        r"\/p\/[^\"'<>\\\s]+",
        r"\/item\/[^\"'<>\\\s]+",
        r"\/sku\/[^\"'<>\\\s]+",
    ]

    saida: list[str] = []
    vistos: set[str] = set()

    for padrao in padroes:
        for raw in re.findall(padrao, html, flags=re.I):
            raw = safe_str(raw).replace("\\/", "/")
            url = normalizar_link_crawl(base_url, raw)

            if not url or url in vistos:
                continue

            if not url_valida_para_crawl(base_url, url):
                continue

            if _url_ruim(url):
                continue

            vistos.add(url)
            saida.append(url)

    return saida


def _descobrir_links_por_bfs(
    session: requests.Session,
    base_url: str,
    *,
    max_paginas: int,
    max_produtos: int,
    max_segundos: int,
) -> list[str]:
    inicio = time.time()
    base_url = normalizar_url(base_url)
    fila = deque([base_url, _raiz(base_url)])
    visitados: set[str] = set()
    produtos: list[str] = []
    produtos_vistos: set[str] = set()

    while fila:
        if len(visitados) >= max_paginas:
            break

        if len(produtos) >= max_produtos:
            break

        if time.time() - inicio > max_segundos:
            break

        pagina = fila.popleft()

        if pagina in visitados:
            continue

        visitados.add(pagina)

        html = _fetch(session, pagina)
        if not html:
            continue

        if _html_tem_produto(html) and not _parece_categoria_url(pagina):
            if pagina not in produtos_vistos:
                produtos_vistos.add(pagina)
                produtos.append(pagina)

        try:
            links_categoria, links_produto = extrair_links_pagina(base_url, pagina, html)
        except Exception:
            links_categoria, links_produto = [], []

        links_js = _extrair_links_js(base_url, html)

        for link in links_produto + links_js:
            if not link or link in produtos_vistos:
                continue

            if not _mesmo_host(base_url, link):
                continue

            if _url_ruim(link):
                continue

            if _parece_produto_url(link) or not _parece_categoria_url(link):
                produtos_vistos.add(link)
                produtos.append(link)

            if len(produtos) >= max_produtos:
                break

        for link in links_categoria:
            if not link:
                continue

            if link in visitados or link in fila:
                continue

            if not _mesmo_host(base_url, link):
                continue

            if _url_ruim(link):
                continue

            fila.append(link)

        soup = BeautifulSoup(html, "lxml")

        for a in soup.find_all("a", href=True):
            href = normalizar_link_crawl(base_url, safe_str(a.get("href")))

            if not href:
                continue

            if href in visitados or href in fila:
                continue

            if not _mesmo_host(base_url, href):
                continue

            if _url_ruim(href):
                continue

            texto = safe_str(a.get_text(" ", strip=True))
            contexto = normalizar_texto(f"{href} {texto}")

            if _parece_produto_url(href):
                if href not in produtos_vistos:
                    produtos_vistos.add(href)
                    produtos.append(href)

            elif _parece_categoria_url(href) or any(
                x in contexto for x in ("produtos", "categoria", "departamento", "ver mais")
            ):
                fila.append(href)

    return produtos[:max_produtos]


def _descobrir_links_produtos(
    session: requests.Session,
    base_url: str,
    *,
    usar_sitemap: bool,
    usar_home: bool,
    max_paginas: int,
    max_produtos: int,
    max_segundos: int,
    auth_context: dict[str, Any] | None,
) -> list[str]:
    encontrados: list[str] = []
    vistos: set[str] = set()

    def add_many(lista: list[str]) -> None:
        for url in lista:
            url = normalizar_link_crawl(base_url, url)

            if not url or url in vistos:
                continue

            if not url_valida_para_crawl(base_url, url):
                continue

            if _url_ruim(url):
                continue

            vistos.add(url)
            encontrados.append(url)

    if usar_sitemap:
        _log("[CRAWLER_ENGINE] Lendo sitemap.")
        sitemap_urls = _buscar_sitemaps(session, base_url)
        produtos_sitemap = [u for u in sitemap_urls if _parece_produto_url(u)]
        add_many(produtos_sitemap)

    if len(encontrados) < max_produtos and usar_home:
        _log("[CRAWLER_ENGINE] Lendo home, categorias, paginações e JS.")
        try:
            descobertos = descobrir_produtos_no_dominio(
                base_url,
                max_paginas=max_paginas,
                max_produtos=max_produtos,
                max_segundos=max_segundos,
                auth_context=auth_context,
            )
            add_many(descobertos)
        except Exception as exc:
            _log(f"[CRAWLER_ENGINE] descoberta via links module falhou: {exc}")

    if len(encontrados) < max_produtos and usar_home:
        try:
            bfs = _descobrir_links_por_bfs(
                session,
                base_url,
                max_paginas=max_paginas,
                max_produtos=max_produtos,
                max_segundos=max_segundos,
            )
            add_many(bfs)
        except Exception as exc:
            _log(f"[CRAWLER_ENGINE] BFS fallback falhou: {exc}")

    if not encontrados:
        html = _fetch(session, base_url)

        if html and _html_tem_produto(html):
            add_many([base_url])

    return encontrados[:max_produtos]


def _produto_valido(produto: dict[str, Any]) -> bool:
    nome = safe_str(produto.get("descricao") or produto.get("nome"))
    url = safe_str(produto.get("url_produto"))
    preco = safe_str(produto.get("preco"))
    imagens = safe_str(produto.get("url_imagens") or produto.get("imagens"))
    codigo = safe_str(produto.get("codigo") or produto.get("sku"))
    gtin = safe_str(produto.get("gtin"))

    score = 0

    if nome and len(nome) >= 4:
        score += 3

    if url:
        score += 1

    if preco:
        score += 2

    if imagens:
        score += 1

    if codigo:
        score += 1

    if gtin:
        score += 1

    return score >= 3


def _extrair_um_produto(session: requests.Session, url_produto: str) -> dict[str, Any]:
    html = _fetch(session, url_produto)
    if not html:
        return {}

    produto = extrair_detalhes_heuristicos(url_produto, html)

    if not isinstance(produto, dict):
        return {}

    produto.setdefault("url_produto", url_produto)

    if not safe_str(produto.get("descricao")):
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.select_one("h1")
        titulo = safe_str(h1.get_text(" ", strip=True) if h1 else "")

        if titulo:
            produto["descricao"] = titulo

    return produto if _produto_valido(produto) else {}


def _normalizar_saida(produtos: list[dict[str, Any]]) -> pd.DataFrame:
    linhas: list[dict[str, Any]] = []

    for p in produtos:
        if not isinstance(p, dict):
            continue

        linha = {
            "url_produto": safe_str(p.get("url_produto")),
            "nome": safe_str(p.get("descricao") or p.get("nome")),
            "sku": safe_str(p.get("codigo") or p.get("sku")),
            "marca": safe_str(p.get("marca")),
            "categoria": safe_str(p.get("categoria")),
            "estoque": safe_str(p.get("quantidade") or p.get("estoque") or "1"),
            "preco": safe_str(p.get("preco")),
            "gtin": _limpar_gtin(safe_str(p.get("gtin"))),
            "descricao": safe_str(p.get("descricao_detalhada") or p.get("descricao") or p.get("nome")),
            "imagens": safe_str(p.get("url_imagens") or p.get("imagens")),
        }

        if linha["nome"] or linha["url_produto"]:
            linhas.append(linha)

    df = pd.DataFrame(linhas)

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if df.empty:
        return df[OUTPUT_COLUMNS]

    df["_dedupe"] = (
        df["url_produto"].astype(str).str.strip().str.lower()
        + "|"
        + df["sku"].astype(str).str.strip().str.lower()
        + "|"
        + df["nome"].astype(str).str.strip().str.lower()
        + "|"
        + df["preco"].astype(str).str.strip().str.lower()
    )

    df = df.drop_duplicates(subset=["_dedupe"], keep="first")
    df = df.drop(columns=["_dedupe"], errors="ignore")

    return df[OUTPUT_COLUMNS].reset_index(drop=True)


def _mesclar_dataframes(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    partes = [df for df in dfs if isinstance(df, pd.DataFrame) and not df.empty]

    if not partes:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = pd.concat(partes, ignore_index=True)

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["_score"] = df.apply(lambda r: _score_linha(r.to_dict()), axis=1)
    df["_dedupe"] = (
        df["url_produto"].astype(str).str.strip().str.lower()
        + "|"
        + df["sku"].astype(str).str.strip().str.lower()
        + "|"
        + df["nome"].astype(str).str.strip().str.lower()
    )

    df = df.sort_values("_score", ascending=False)
    df = df.drop_duplicates(subset=["_dedupe"], keep="first")
    df = df.drop(columns=["_score", "_dedupe"], errors="ignore")

    return df[OUTPUT_COLUMNS].reset_index(drop=True)


def run_crawler(
    base_url: str,
    *,
    auth_context: dict[str, Any] | None = None,
    varrer_site_completo: bool = True,
    sitemap_completo: bool = True,
    max_workers: int = 12,
    limite: int | None = None,
    limite_paginas: int | None = None,
    usar_sitemap: bool = True,
    usar_home: bool = True,
    usar_categoria: bool = True,
    modo: str = "completo",
    preferir_playwright: bool = False,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Entrada principal usada pelo SiteAgent.

    Nova ordem:
    1. Universal DOM Scraper: detecta tabela/listagem/card automaticamente.
    2. JSON-LD Product.
    3. Fallback antigo: sitemap + links de produtos + extração heurística.
    """

    inicio = time.time()
    url = normalizar_url(base_url)

    if not url:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    max_workers = max(1, min(int(max_workers or 8), 24))

    if limite is None:
        limite_produtos = 8000 if varrer_site_completo else 300
    else:
        try:
            limite_produtos = max(1, int(limite))
        except Exception:
            limite_produtos = 8000 if varrer_site_completo else 300

    if limite_paginas is None:
        max_paginas = 600 if varrer_site_completo else 80
    else:
        try:
            max_paginas = max(1, int(limite_paginas))
        except Exception:
            max_paginas = 600 if varrer_site_completo else 80

    max_segundos = int(kwargs.get("max_segundos", 900 if varrer_site_completo else 240))
    session = _criar_session(auth_context)

    _log(
        "[CRAWLER_ENGINE] Iniciado "
        f"| modo=universal_data_scraper "
        f"| url={url} "
        f"| sitemap={usar_sitemap and sitemap_completo} "
        f"| home={usar_home} "
        f"| max_paginas={max_paginas} "
        f"| limite_produtos={limite_produtos} "
        f"| workers={max_workers}"
    )

    dfs_resultado: list[pd.DataFrame] = []

    try:
        df_universal = _universal_scrape_paginas(
            session,
            url,
            limite_paginas=max(1, min(max_paginas, 40 if not varrer_site_completo else max_paginas)),
            limite_produtos=limite_produtos,
            max_segundos=max(60, int(max_segundos * 0.45)),
        )

        if not df_universal.empty:
            _log(f"[UNIVERSAL_SCRAPER] Linhas capturadas por estrutura repetida: {len(df_universal)}")
            dfs_resultado.append(df_universal)

            if len(df_universal) >= limite_produtos or len(df_universal) >= 20:
                df_final_parcial = _mesclar_dataframes(dfs_resultado).head(limite_produtos)
                _log(
                    "[CRAWLER_ENGINE] Finalizado pelo motor universal "
                    f"| produtos={len(df_final_parcial)} "
                    f"| tempo={time.time() - inicio:.1f}s"
                )
                return df_final_parcial

    except Exception as exc:
        _log(f"[UNIVERSAL_SCRAPER] Falhou; usando fallback antigo: {exc}")

    links = _descobrir_links_produtos(
        session,
        url,
        usar_sitemap=bool(usar_sitemap and sitemap_completo),
        usar_home=bool(usar_home or usar_categoria),
        max_paginas=max_paginas,
        max_produtos=limite_produtos,
        max_segundos=max_segundos,
        auth_context=auth_context,
    )

    links = links[:limite_produtos]
    _log(f"[CRAWLER_ENGINE] Links de produto candidatos: {len(links)}")

    produtos: list[dict[str, Any]] = []

    if not links:
        html_home = _fetch(session, url)

        if html_home:
            direto = extrair_detalhes_heuristicos(url, html_home)

            if isinstance(direto, dict) and _produto_valido(direto):
                produtos.append(direto)

        df_direto = _normalizar_saida(produtos)
        dfs_resultado.append(df_direto)

        df_final = _mesclar_dataframes(dfs_resultado).head(limite_produtos)

        _log(f"[CRAWLER_ENGINE] Finalizado com {len(df_final)} produto(s).")
        return df_final

    def worker(link: str) -> dict[str, Any]:
        try:
            return _extrair_um_produto(session, link)
        except Exception:
            return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(worker, link): link for link in links}

        for idx, futuro in enumerate(concurrent.futures.as_completed(futuros), start=1):
            if time.time() - inicio > max_segundos:
                _log("[CRAWLER_ENGINE] Tempo máximo atingido; retornando parcial.")
                break

            try:
                produto = futuro.result()
            except Exception:
                produto = {}

            if produto:
                produtos.append(produto)

            if idx % 25 == 0:
                _log(
                    f"[CRAWLER_ENGINE] Progresso: {idx}/{len(links)} páginas lidas "
                    f"| produtos válidos={len(produtos)}"
                )

            if len(produtos) >= limite_produtos:
                break

    df_produtos = _normalizar_saida(produtos)
    dfs_resultado.append(df_produtos)

    df = _mesclar_dataframes(dfs_resultado).head(limite_produtos)

    _log(
        "[CRAWLER_ENGINE] Concluído "
        f"| links={len(links)} "
        f"| produtos={len(df)} "
        f"| tempo={time.time() - inicio:.1f}s"
    )

    return df
