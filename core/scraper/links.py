import json
import re
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch


def _normalizar(link):
    if not link:
        return ""
    link = str(link).strip()
    if "#" in link:
        link = link.split("#")[0]
    return link.rstrip("/")


def _eh_link_valido(link):
    if not link:
        return False

    lk = link.lower()

    bloqueados = [
        "whatsapp",
        "facebook",
        "instagram",
        "youtube",
        "mailto:",
        "tel:",
        "javascript:",
        "/carrinho",
        "/cart",
        "/checkout",
        "/login",
        "/account",
        "/cliente",
        "/favoritos",
        "/wishlist",
    ]

    for b in bloqueados:
        if b in lk:
            return False

    return True


def _eh_link_produto(link):
    lk = (link or "").lower()

    sinais = [
        "/produto",
        "/product",
        "/p/",
        "-p",
        ".html",
    ]

    return any(s in lk for s in sinais)


def _adicionar_link(links, link):
    link = _normalizar(link)
    if link and _eh_link_valido(link) and _eh_link_produto(link):
        links.append(link)


def _extrair_links_de_anchors(soup, url_base):
    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        link = urljoin(url_base, href)
        _adicionar_link(links, link)

    return links


def _extrair_links_de_scripts(html, url_base):
    links = []

    # qualquer URL absoluta/relativa que pareça produto
    padroes = [
        r'https?://[^\s"\'<>]+',
        r'/(?:produto|product|p)/[^\s"\'<>]+',
        r'[A-Za-z0-9\-_\/]+-p(?:/[A-Za-z0-9\-_\/]+)?',
        r'[A-Za-z0-9\-_\/]+\.html',
    ]

    for padrao in padroes:
        for achado in re.findall(padrao, html, flags=re.IGNORECASE):
            link = achado
            if not link.startswith("http"):
                link = urljoin(url_base, link)
            _adicionar_link(links, link)

    return links


def _extrair_links_jsonld(soup, url_base):
    links = []

    for script in soup.find_all("script", type="application/ld+json"):
        texto = script.string or script.get_text(" ", strip=True)
        if not texto:
            continue

        try:
            dado = json.loads(texto)
        except Exception:
            continue

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.lower() in ["url", "@id"] and isinstance(v, str):
                        link = urljoin(url_base, v)
                        _adicionar_link(links, link)
                    else:
                        walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(dado)

    return links


def _extrair_links_pagina(html, url_base, pagina_label=""):
    soup = BeautifulSoup(html, "html.parser")

    links = []
    links.extend(_extrair_links_de_anchors(soup, url_base))
    links.extend(_extrair_links_de_scripts(html, url_base))
    links.extend(_extrair_links_jsonld(soup, url_base))

    vistos = set()
    unicos = []
    for link in links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

    log(f"{pagina_label} links_produto_unicos={len(unicos)}")
    if unicos:
        log(f"{pagina_label} primeiros_links={unicos[:5]}")

    return unicos


def _descobrir_total_paginas(html):
    soup = BeautifulSoup(html, "html.parser")
    numeros = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        texto = a.get_text(" ", strip=True)

        if texto.isdigit():
            try:
                numeros.append(int(texto))
            except Exception:
                pass

        try:
            qs = parse_qs(urlparse(href).query)
            if "page" in qs:
                for v in qs["page"]:
                    if str(v).isdigit():
                        numeros.append(int(v))
        except Exception:
            pass

    if numeros:
        return max(numeros)

    return 1


def coletar_links_site(url_base, max_paginas=100):
    todos = []
    vistos = set()

    def add_links(links):
        novos = 0
        for link in links:
            if link not in vistos:
                vistos.add(link)
                todos.append(link)
                novos += 1
        return novos

    # página 1 real
    urls_teste = [
        url_base,
        f"{url_base}?page=1",
        f"{url_base}/page/1",
        f"{url_base}/pagina/1",
    ]

    melhor_html = None
    melhor_links = []
    melhor_url = ""

    for url in urls_teste:
        html = fetch(url)
        if not html:
            continue

        links = _extrair_links_pagina(html, url, f"[TESTE {url}]")

        if len(links) > len(melhor_links):
            melhor_links = links
            melhor_html = html
            melhor_url = url

    if not melhor_html:
        log("ERRO: nenhuma versão da página 1 funcionou")
        return []

    log(f"Página 1 REAL detectada: {melhor_url}")
    log(f"Links página 1: {len(melhor_links)}")

    add_links(melhor_links)

    total_paginas = _descobrir_total_paginas(melhor_html)
    total_paginas = max(1, min(total_paginas, max_paginas))
    log(f"Paginação detectada: {total_paginas}")

    paginas_sem_novos = 0

    for pagina in range(2, total_paginas + 1):
        urls_pagina = [
            f"{url_base}?page={pagina}",
            f"{url_base}/page/{pagina}",
            f"{url_base}/pagina/{pagina}",
        ]

        melhor_links_pagina = []

        for url in urls_pagina:
            html = fetch(url)
            if not html:
                continue

            links = _extrair_links_pagina(html, url, f"[PAGINA {pagina} {url}]")
            if len(links) > len(melhor_links_pagina):
                melhor_links_pagina = links

        novos = add_links(melhor_links_pagina)
        log(f"Página {pagina}: {novos} novos links")

        if novos == 0:
            paginas_sem_novos += 1
        else:
            paginas_sem_novos = 0

        if paginas_sem_novos >= 5:
            log("Parando: 5 páginas seguidas sem links novos")
            break

    log(f"TOTAL LINKS COLETADOS: {len(todos)}")
    return todos
