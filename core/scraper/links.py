from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch


def _normalizar_link_produto(link: str) -> str:
    if not link:
        return ""

    link = link.strip()

    # remove fragmentos
    if "#" in link:
        link = link.split("#")[0]

    # remove barra final duplicada
    if link.endswith("/"):
        link = link[:-1]

    return link


def _parece_link_produto(link: str) -> bool:
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
        "/categoria",
        "/category",
        "/buscar",
        "/search",
    ]

    for b in bloqueados:
        if b in lk:
            return False

    pistas_produto = [
        "/produto",
        "/products/",
        "/product/",
        "-p",
    ]

    return any(p in lk for p in pistas_produto)


def _extrair_links_pagina(html: str, url_base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        link = urljoin(url_base, href)
        link = _normalizar_link_produto(link)

        if _parece_link_produto(link):
            links.append(link)

    # remove duplicados preservando ordem
    vistos = set()
    unicos = []
    for link in links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

    return unicos


def _descobrir_total_paginas(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    numeros = []

    # pega links de paginação
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        texto = a.get_text(" ", strip=True)

        # número no texto do botão/link
        if texto.isdigit():
            try:
                numeros.append(int(texto))
            except Exception:
                pass

        # número no parâmetro ?page=
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


def coletar_links_site(url_base: str, limite_paginas: int = 100) -> list[str]:
    """
    Coleta links de produto percorrendo as páginas até:
    - acabar paginação
    - ou ficar sem links novos
    """

    todos_links = []
    vistos = set()

    # primeira página
    html_inicial = fetch(url_base)
    if not html_inicial:
        log(f"Não foi possível abrir a página inicial: {url_base}")
        return []

    total_paginas = _descobrir_total_paginas(html_inicial)
    total_paginas = max(1, min(total_paginas, limite_paginas))

    log(f"Paginação detectada: {total_paginas} páginas")

    # tenta coletar da página inicial
    links_iniciais = _extrair_links_pagina(html_inicial, url_base)
    for link in links_iniciais:
        if link not in vistos:
            vistos.add(link)
            todos_links.append(link)

    # percorre as demais
    paginas_sem_novidade = 0

    for pagina in range(2, total_paginas + 1):
        url_pagina = f"{url_base}?page={pagina}"
        html = fetch(url_pagina)

        if not html:
            log(f"Falha ao carregar página {pagina}: {url_pagina}")
            continue

        links = _extrair_links_pagina(html, url_base)

        novos = 0
        for link in links:
            if link not in vistos:
                vistos.add(link)
                todos_links.append(link)
                novos += 1

        log(f"Página {pagina}: {novos} links novos")

        if novos == 0:
            paginas_sem_novidade += 1
        else:
            paginas_sem_novidade = 0

        # se várias páginas seguidas não trouxerem novidade, para
        if paginas_sem_novidade >= 3:
            log("Parando coleta: 3 páginas seguidas sem links novos")
            break

    log(f"Total final de links coletados: {len(todos_links)}")
    return todos_links
