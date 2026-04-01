from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch


def coletar_links_site(url_base):
    links = []

    for p in range(1, 6):
        html = fetch(f"{url_base}?page={p}")
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        candidatos = []
        candidatos.extend(soup.select("a[href*='produto']"))
        candidatos.extend(soup.select("a[href*='product']"))
        candidatos.extend(soup.find_all("a", href=True))

        for a in candidatos:
            href = a.get("href", "")
            if not href:
                continue

            link = urljoin(url_base, href)

            if any(x in link.lower() for x in ["/produto", "/product", "/p/"]):
                links.append(link)

    vistos = set()
    unicos = []
    for lnk in links:
        if lnk not in vistos:
            vistos.add(lnk)
            unicos.append(lnk)

    log(f"Links únicos coletados: {len(unicos)}")
    return unicos
