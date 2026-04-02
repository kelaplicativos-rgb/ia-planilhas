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
    return "/produto/" in lk or "/product/" in lk or "/p/" in lk


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


def _adicionar_link_produto(mapa_links: dict, link: str):
    link = _normalizar_basico(link)
    if not link or not _eh_link_valido(link):
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
        mapa_links[produto_id] = link_canonico
    else:
        mapa_links[link_canonico] = link_canonico


def _extrair_links_de_anchors(soup, url_base):
    mapa = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue
        link = urljoin(url_base, href)
        _adicionar_link_produto(mapa, link)

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
                        _adicionar_link_produto(mapa, urljoin(url_base, v))
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
        for achado in re.findall(padrao, html, flags=re.IGNORECASE):
            link = achado if achado.startswith("http") else urljoin(url_base, achado)
            _adicionar_link_produto(mapa, link)

    return list(mapa.values())


def _extrair_links_categoria(soup, url_base):
    """
    Descobre páginas de categoria para depois paginar nelas também.
    """
    categorias = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue

        link = urljoin(url_base, href)
        lk = link.lower()

        # ignora links de produto; queremos só páginas-lista
        if _eh_link_produto(lk):
            continue

        if not _eh_link_valido(lk):
            continue

        if not _dominio_aceito(link):
            continue

        # bons sinais de categoria/listagem
        sinais = [
            "/categoria/",
            "/produtos",
            "/categoria",
        ]

        texto = limpar(a.get_text(" ", strip=True)).lower()

        if any(s in lk for s in sinais) or texto in {
            "produtos",
            "cabos",
            "fone de ouvido",
            "carregador celular",
            "caixa de som",
            "mouse",
        }:
            categorias[link.rstrip("/")] = link.rstrip("/")

    return list(categorias.values())


def _extrair_links_pagina(html, url_base, pagina_label=""):
    soup = BeautifulSoup(html, "html.parser")
    mapa_final = {}

    for grupo in [
        _extrair_links_de_anchors(soup, url_base),
        _extrair_links_de_jsonld(soup, url_base),
        _extrair_links_de_scripts(html, url_base),
    ]:
        for link in grupo:
            _adicionar_link_produto(mapa_final, link)

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


def _coletar_de_uma_base(base_url, max_paginas, todos):
    paginas_sem_novos = 0

    def add_links(links):
        antes = len(todos)
        for link in links:
            _adicionar_link_produto(todos, link)
        return len(todos) - antes

    html_1 = fetch(base_url)
    if not html_1:
        return

    total_paginas = _descobrir_total_paginas(html_1)
    total_paginas = max(1, min(total_paginas, max_paginas))
    log(f"[BASE {base_url}] paginação detectada: {total_paginas}")

    links_1 = _extrair_links_pagina(html_1, base_url, f"[BASE {base_url} PAG 1]")
    add_links(links_1)

    for pagina in range(2, total_paginas + 1):
        urls_pagina = [
            f"{base_url.rstrip('/')}/?page={pagina}",
            f"{base_url.rstrip('/')}/page/{pagina}",
            f"{base_url.rstrip('/')}/pagina/{pagina}",
        ]

        melhor_links_pagina = []

        for url in urls_pagina:
            html = fetch(url)
            if not html:
                continue

            links = _extrair_links_pagina(html, base_url, f"[BASE {base_url} PAG {pagina} {url}]")
            if len(links) > len(melhor_links_pagina):
                melhor_links_pagina = links

        novos = add_links(melhor_links_pagina)
        log(f"[BASE {base_url}] página {pagina}: {novos} novos links")

        if novos == 0:
            paginas_sem_novos += 1
        else:
            paginas_sem_novos = 0

        if paginas_sem_novos >= 2:
            break


def coletar_links_site(url_base, max_paginas=30):
    base = url_base.rstrip("/")
    todos = {}

    melhor_url, melhor_html, melhor_links = _coletar_melhor_pagina_1(base)

    if not melhor_html:
        log("ERRO: nenhuma versão da página 1 funcionou")
        return []

    log(f"Página 1 REAL detectada: {melhor_url}")
    log(f"Links página 1: {len(melhor_links)}")

    for link in melhor_links:
        _adicionar_link_produto(todos, link)

    # 1) paginação principal
    _coletar_de_uma_base(base, max_paginas=max_paginas, todos=todos)

    # 2) categorias descobertas na home
    soup = BeautifulSoup(melhor_html, "html.parser")
    categorias = _extrair_links_categoria(soup, base)
    log(f"Categorias descobertas: {len(categorias)}")

    for categoria in categorias[:20]:
        _coletar_de_uma_base(categoria, max_paginas=10, todos=todos)

    links_finais = list(todos.values())
    log(f"TOTAL LINKS COLETADOS: {len(links_finais)}")

    return links_finais
