import json
import re
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch
from core.utils import limpar


DOMINIO_PRINCIPAL = "https://megacentereletronicos.com.br"
DOMINIOS_ACEITOS = {
    "megacentereletronicos.com.br",
    "www.megacentereletronicos.com.br",
    "mega-center-eletronicos.stoqui.shop",
}


def _normalizar_basico(link: str) -> str:
    link = limpar(link)
    if not link:
        return ""

    if "#" in link:
        link = link.split("#")[0]

    return link.rstrip("/")


def _dominio_aceito(link: str) -> bool:
    try:
        host = urlparse(link).netloc.lower().strip()
        return host in DOMINIOS_ACEITOS
    except Exception:
        return False


def _eh_link_valido(link: str) -> bool:
    if not link:
        return False

    lk = link.lower()

    bloqueados = [
        "javascript:",
        "mailto:",
        "tel:",
        "whatsapp",
        "instagram",
        "facebook",
        "youtube",
        "/carrinho",
        "/checkout",
        "/login",
        "/conta",
        "/cliente",
        "/favoritos",
        "/wishlist",
        "/blog",
        "/sobre",
        "/contato",
    ]

    return not any(b in lk for b in bloqueados)


def _eh_link_produto(link: str) -> bool:
    lk = (link or "").lower()

    if "/produto/" in lk:
        return True
    if "/product/" in lk:
        return True
    if "/p/" in lk:
        return True

    return False


def _extrair_id_produto(link: str) -> str:
    if not link:
        return ""

    padroes = [
        r"/produto/(\d+)",
        r"/product/(\d+)",
        r"/p/(\d+)",
    ]

    for padrao in padroes:
        m = re.search(padrao, link, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    return ""


def _canonizar_link_produto(link: str) -> str:
    link = _normalizar_basico(link)
    if not link:
        return ""

    try:
        parsed = urlparse(link)
        path = parsed.path or ""
        if not path:
            return ""

        return f"{DOMINIO_PRINCIPAL}{path}".rstrip("/")
    except Exception:
        return link


def _adicionar_link(mapa_links: dict, link: str):
    link = _normalizar_basico(link)
    if not link:
        return

    if not _eh_link_valido(link):
        return

    if not _eh_link_produto(link):
        return

    if not _dominio_aceito(link):
        return

    link_canonico = _canonizar_link_produto(link)
    if not link_canonico:
        return

    produto_id = _extrair_id_produto(link_canonico)

    if produto_id:
        if produto_id not in mapa_links:
            mapa_links[produto_id] = link_canonico
        return

    if link_canonico not in mapa_links:
        mapa_links[link_canonico] = link_canonico


def _extrair_links_de_anchors(soup, url_base):
    mapa = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue

        link = urljoin(url_base, href)
        _adicionar_link(mapa, link)

    return list(mapa.values())


def _extrair_links_de_jsonld(soup, url_base):
    mapa = {}

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
                        _adicionar_link(mapa, link)
                    else:
                        walk(v)

            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(dado)

    return list(mapa.values())


def _extrair_links_de_scripts(html, url_base):
    mapa = {}

    padroes = [
        r'https?://[^\s"\'<>]+',
        r'/(?:produto|product|p)/[^\s"\'<>]+',
    ]

    for padrao in padroes:
        achados = re.findall(padrao, html, flags=re.IGNORECASE)
        for achado in achados:
            link = achado
            if not str(link).startswith("http"):
                link = urljoin(url_base, link)
            _adicionar_link(mapa, link)

    return list(mapa.values())


def _extrair_links_pagina(html, url_base, pagina_label=""):
    soup = BeautifulSoup(html, "html.parser")
    mapa_final = {}

    for grupo in [
        _extrair_links_de_anchors(soup, url_base),
        _extrair_links_de_jsonld(soup, url_base),
        _extrair_links_de_scripts(html, url_base),
    ]:
        for link in grupo:
            _adicionar_link(mapa_final, link)

    unicos = list(mapa_final.values())

    log(f"{pagina_label} links_produto_unicos={len(unicos)}")
    if unicos:
        log(f"{pagina_label} primeiros_links={unicos[:5]}")

    return unicos


def _descobrir_total_paginas(html):
    soup = BeautifulSoup(html, "html.parser")
    numeros = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        texto = limpar(a.get_text(" ", strip=True))

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

    return max(numeros) if numeros else 1


def _coletar_melhor_pagina_1(url_base):
    base = url_base.rstrip("/")

    urls_teste = [
        base,
        f"{base}/?page=1",
        f"{base}/page/1",
        f"{base}/pagina/1",
    ]

    melhor_html = None
    melhor_links = []
    melhor_url = ""

    for url in urls_teste:
        html = fetch(url)
        if not html:
            log(f"[TESTE PÁGINA 1] falhou: {url}")
            continue

        links = _extrair_links_pagina(html, base, f"[TESTE {url}]")

        if len(links) > len(melhor_links):
            melhor_html = html
            melhor_links = links
            melhor_url = url

    return melhor_url, melhor_html, melhor_links


def coletar_links_site(url_base, max_paginas=30):
    base = url_base.rstrip("/")
    todos = {}
    paginas_sem_novos = 0

    def add_links(links):
        antes = len(todos)
        for link in links:
            _adicionar_link(todos, link)
        return len(todos) - antes

    melhor_url, melhor_html, melhor_links = _coletar_melhor_pagina_1(base)

    if not melhor_html:
        log("ERRO: nenhuma versão da página 1 funcionou")
        return []

    log(f"Página 1 REAL detectada: {melhor_url}")
    log(f"Links página 1: {len(melhor_links)}")

    add_links(melhor_links)

    total_paginas = _descobrir_total_paginas(melhor_html)
    total_paginas = max(1, min(total_paginas, max_paginas))
    log(f"Paginação detectada: {total_paginas}")

    for pagina in range(2, total_paginas + 1):
        urls_pagina = [
            f"{base}/?page={pagina}",
            f"{base}/page/{pagina}",
            f"{base}/pagina/{pagina}",
        ]

        melhor_links_pagina = []

        for url in urls_pagina:
            html = fetch(url)
            if not html:
                continue

            links = _extrair_links_pagina(html, base, f"[PAGINA {pagina} {url}]")

            if len(links) > len(melhor_links_pagina):
                melhor_links_pagina = links

        novos = add_links(melhor_links_pagina)
        log(f"Página {pagina}: {novos} novos links")

        if novos == 0:
            paginas_sem_novos += 1
        else:
            paginas_sem_novos = 0

        if paginas_sem_novos >= 3:
            log("Parando: 3 páginas seguidas sem links novos")
            break

    links_finais = list(todos.values())
    log(f"TOTAL LINKS COLETADOS: {len(links_finais)}")

    return links_finais
