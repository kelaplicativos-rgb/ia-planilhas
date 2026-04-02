from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch


def _normalizar(link):
    if not link:
        return ""
    link = link.strip()
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
    ]

    for b in bloqueados:
        if b in lk:
            return False

    return True


def _extrair_links_pagina(html, url_base):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        link = urljoin(url_base, href)
        link = _normalizar(link)

        if not _eh_link_valido(link):
            continue

        # mais agressivo para não perder produto
        if any(x in link.lower() for x in [
            "/produto",
            "/product",
            "/p/",
            "-p",
            ".html"
        ]):
            links.append(link)

    vistos = set()
    unicos = []
    for link in links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

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

    html_inicial = fetch(url_base)
    if not html_inicial:
        log(f"Não foi possível abrir a página inicial: {url_base}")
        return []

    total_paginas = _descobrir_total_paginas(html_inicial)
    total_paginas = max(1, min(total_paginas, max_paginas))
    log(f"Paginação detectada: {total_paginas}")

    links_iniciais = _extrair_links_pagina(html_inicial, url_base)
    for link in links_iniciais:
        if link not in vistos:
            vistos.add(link)
            todos.append(link)

    paginas_sem_novos = 0

    for pagina in range(2, total_paginas + 1):
        url = f"{url_base}?page={pagina}"
        html = fetch(url)

        if not html:
            log(f"Erro página {pagina}")
            continue

        links = _extrair_links_pagina(html, url_base)

        novos = 0
        for link in links:
            if link not in vistos:
                vistos.add(link)
                todos.append(link)
                novos += 1

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
