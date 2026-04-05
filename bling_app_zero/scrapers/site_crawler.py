import posixpath
import re
import xml.etree.ElementTree as ET
from collections import deque
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

from .extrator_produto import classificar_pagina, extrair_produto_html
from .fetcher import baixar_html


IGNORED_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.pdf', '.zip', '.rar', '.7z',
    '.mp4', '.avi', '.mov', '.wmv', '.doc', '.docx', '.xls', '.xlsx', '.csv',
)

PRODUCT_HINTS = (
    '/produto', '/product', '/p/', '/pd-', '/item/', '/sku/', '/shop/',
)
CATEGORY_HINTS = (
    '/categoria', '/categorias', '/category', '/departamento', '/colecao',
    '/colecoes', '/collections', '/catalog', '/loja/', '/shop/',
)


def _normalizar_url(url: str) -> str:
    url = (url or '').strip()
    if not url:
        return ''
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    return url



def _canonicalizar_url(url: str) -> str:
    url = _normalizar_url(url)
    if not url:
        return ''

    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or 'https'
    netloc = parsed.netloc.lower()
    path = parsed.path or '/'
    path = re.sub(r'/+', '/', path)
    if path != '/':
        path = path.rstrip('/')
    return urlunparse((scheme, netloc, path, '', '', ''))



def _mesmo_dominio(url: str, dominio_base: str) -> bool:
    try:
        host = (urlparse(url).netloc or '').lower()
    except Exception:
        return False
    return host == dominio_base or host.endswith('.' + dominio_base)



def _url_ignorada(url: str) -> bool:
    baixa = url.lower()
    return (
        any(ext in baixa for ext in IGNORED_EXTENSIONS)
        or 'mailto:' in baixa
        or 'tel:' in baixa
        or 'whatsapp' in baixa
        or '/cart' in baixa
        or '/checkout' in baixa
        or '/login' in baixa
        or '/account' in baixa
    )



def _score_link(url: str) -> int:
    baixa = url.lower()
    score = 0
    if any(token in baixa for token in PRODUCT_HINTS):
        score += 5
    if any(token in baixa for token in CATEGORY_HINTS):
        score += 3
    if re.search(r'/[a-z0-9\-_]+/p$', baixa):
        score += 4
    score += baixa.count('/')
    return score



def _extrair_links(html: str, base_url: str, dominio_base: str) -> List[str]:
    soup = BeautifulSoup(html or '', 'html.parser')
    links: List[str] = []

    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href or href.startswith('#'):
            continue
        absoluto = _canonicalizar_url(urljoin(base_url, href))
        if not absoluto:
            continue
        if not _mesmo_dominio(absoluto, dominio_base):
            continue
        if _url_ignorada(absoluto):
            continue
        links.append(absoluto)

    unicos = sorted(set(links), key=lambda x: (-_score_link(x), x))
    return unicos



def _descobrir_sitemaps(url_base: str, html_home: str) -> List[str]:
    candidatos = [urljoin(url_base, '/sitemap.xml')]
    soup = BeautifulSoup(html_home or '', 'html.parser')

    for link in soup.find_all('link', attrs={'rel': re.compile('sitemap', re.I)}):
        href = link.get('href')
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
        tag = elem.tag.split('}', 1)[-1].lower()
        if tag == 'loc' and elem.text:
            urls.append(elem.text.strip())
            if len(urls) >= limite:
                break
    return urls



def _carregar_urls_do_sitemap(url_base: str, html_home: str, dominio_base: str, limite_total: int = 1500) -> List[str]:
    urls: List[str] = []
    for sitemap_url in _descobrir_sitemaps(url_base, html_home):
        resp = baixar_html(sitemap_url, timeout=25)
        if not resp.get('ok'):
            continue
        bruto = _parse_sitemap_urls(resp.get('html', ''), limite=limite_total)
        for item in bruto:
            canon = _canonicalizar_url(item)
            if canon and _mesmo_dominio(canon, dominio_base) and not _url_ignorada(canon):
                urls.append(canon)
                if len(urls) >= limite_total:
                    return list(dict.fromkeys(urls))
    return list(dict.fromkeys(urls))



def extrair_produtos_de_site(url_inicial: str, limite_paginas: int = 120, limite_produtos: int = 500) -> pd.DataFrame:
    url_inicial = _canonicalizar_url(url_inicial)
    if not url_inicial:
        raise ValueError('Informe uma URL válida do site da loja.')

    home = baixar_html(url_inicial, timeout=25)
    if not home.get('ok'):
        raise ValueError(f"Não foi possível acessar o site informado: {home.get('erro', 'falha desconhecida')}")

    url_base = home.get('url', url_inicial)
    dominio_base = (urlparse(url_base).netloc or '').lower()
    html_home = home.get('html', '')

    fila = deque()
    visitados: Set[str] = set()
    produtos_visitados: Set[str] = set()
    candidatos_sitemap = _carregar_urls_do_sitemap(url_base, html_home, dominio_base)
    candidatos_home = _extrair_links(html_home, url_base, dominio_base)

    sementes = [url_base] + candidatos_sitemap + candidatos_home
    for item in sementes:
        canon = _canonicalizar_url(item)
        if canon and canon not in visitados:
            fila.append(canon)

    linhas: List[Dict] = []
    paginas_processadas = 0

    while fila and paginas_processadas < limite_paginas and len(linhas) < limite_produtos:
        atual = fila.popleft()
        if atual in visitados:
            continue
        visitados.add(atual)

        resp = home if atual == _canonicalizar_url(url_base) else baixar_html(atual, timeout=20)
        paginas_processadas += 1
        if not resp.get('ok'):
            continue

        url_final = _canonicalizar_url(resp.get('url', atual))
        html = resp.get('html', '')
        if not html:
            continue

        classificacao = classificar_pagina(html, url_final)
        if classificacao.get('is_product') and url_final not in produtos_visitados:
            extraido = extrair_produto_html(html, url_final)
            if extraido.get('nome') or extraido.get('descricao'):
                produtos_visitados.add(url_final)
                extraido['erro_scraper'] = ''
                linhas.append(extraido)

        if len(linhas) >= limite_produtos:
            break

        links = _extrair_links(html, url_final, dominio_base)
        for link in links:
            if link in visitados:
                continue
            baixa = link.lower()
            if any(token in baixa for token in PRODUCT_HINTS + CATEGORY_HINTS):
                fila.appendleft(link)
            else:
                fila.append(link)

    if not linhas:
        raise ValueError('Nenhum produto foi encontrado automaticamente no site informado.')

    df = pd.DataFrame(linhas)
    if 'origem_arquivo_ou_url' in df.columns:
        df = df.drop_duplicates(subset=['origem_arquivo_ou_url']).reset_index(drop=True)
    return df
