import json
import re
from html import unescape
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup


PRODUCT_URL_HINTS = (
    '/produto',
    '/product',
    '/p/',
    '/pd-',
    '/shop/',
    '/item/',
    '/sku/',
)

CATEGORY_URL_HINTS = (
    '/categoria',
    '/categorias',
    '/category',
    '/departamento',
    '/colecao',
    '/colecoes',
    '/collections',
    '/catalog',
    '/loja/',
    '/shop/',
)


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ''
    value = unescape(str(value)).replace(' ', ' ').strip()
    value = re.sub(r'\s+', ' ', value)
    return value.strip()



def _only_digits(value: Optional[str]) -> str:
    if not value:
        return ''
    return re.sub(r'\D+', '', str(value))



def _to_price(value: Optional[str]) -> str:
    txt = _clean_text(value)
    if not txt:
        return ''

    txt = txt.replace('R$', '').replace('r$', '').replace(' ', '')
    txt = re.sub(r'[^0-9,.\-]', '', txt)

    if txt.count(',') == 1 and txt.count('.') >= 1:
        txt = txt.replace('.', '').replace(',', '.')
    elif txt.count(',') == 1 and txt.count('.') == 0:
        txt = txt.replace(',', '.')

    return txt



def _pick_first(*values) -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                txt = _clean_text(item)
                if txt:
                    return txt
        else:
            txt = _clean_text(value)
            if txt:
                return txt
    return ''



def _extract_json_objects(raw: str) -> List[dict]:
    if not raw:
        return []

    raw = raw.strip()
    candidatos = [raw]

    if '\n' in raw:
        candidatos.extend([linha.strip() for linha in raw.splitlines() if linha.strip()])

    objetos: List[dict] = []
    for candidato in candidatos:
        try:
            data = json.loads(candidato)
        except Exception:
            continue

        blocos = data if isinstance(data, list) else [data]
        for bloco in blocos:
            if isinstance(bloco, dict):
                objetos.append(bloco)
    return objetos



def _iter_product_objects(obj) -> Iterable[dict]:
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_product_objects(item)
        return

    if not isinstance(obj, dict):
        return

    tipo = str(obj.get('@type', '')).lower()
    if tipo == 'product' or 'product' in tipo.split(','):
        yield obj

    grafo = obj.get('@graph')
    if isinstance(grafo, list):
        for item in grafo:
            yield from _iter_product_objects(item)

    for chave in ('mainEntity', 'itemListElement'):
        valor = obj.get(chave)
        if isinstance(valor, (list, dict)):
            yield from _iter_product_objects(valor)



def _parse_json_ld(soup: BeautifulSoup) -> Dict:
    produtos: List[Dict] = []

    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        raw = script.string or script.get_text(' ', strip=True)
        for bloco in _extract_json_objects(raw):
            produtos.extend(list(_iter_product_objects(bloco)))

    if not produtos:
        return {}

    p = produtos[0]
    offers = p.get('offers', {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}

    brand = p.get('brand')
    if isinstance(brand, dict):
        brand = brand.get('name', '')

    images = p.get('image', [])
    if isinstance(images, str):
        images = [images]
    if not isinstance(images, list):
        images = []

    category = p.get('category', '')
    if isinstance(category, list):
        category = ' > '.join(_clean_text(x) for x in category if _clean_text(x))

    sku = p.get('sku') or p.get('mpn') or ''
    gtin = (
        p.get('gtin13')
        or p.get('gtin12')
        or p.get('gtin14')
        or p.get('gtin8')
        or p.get('gtin')
        or ''
    )

    return {
        'nome': _clean_text(p.get('name', '')),
        'descricao_curta': _clean_text(p.get('description', '')),
        'marca': _clean_text(brand),
        'codigo': _clean_text(sku),
        'gtin': _only_digits(gtin),
        'preco': _to_price(offers.get('price')),
        'moeda': _clean_text(offers.get('priceCurrency', '')),
        'disponibilidade': _clean_text(offers.get('availability', '')),
        'categoria': _clean_text(category),
        'imagens': [_clean_text(x) for x in images if _clean_text(x)],
    }



def _extract_meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find('meta', attrs={'property': prop})
    if tag and tag.get('content'):
        return _clean_text(tag['content'])

    tag = soup.find('meta', attrs={'name': prop})
    if tag and tag.get('content'):
        return _clean_text(tag['content'])

    return ''



def _find_price_in_text(html: str) -> str:
    padroes = [
        r'R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}',
        r'R\$\s?\d+,\d{2}',
        r'price[^0-9]{0,10}(\d+[\.,]\d{2})',
    ]

    for padrao in padroes:
        achados = re.findall(padrao, html or '', flags=re.IGNORECASE)
        if achados:
            valor = achados[0] if isinstance(achados[0], str) else achados[0][0]
            return _to_price(valor)

    return ''



def _find_gtin_in_text(html: str) -> str:
    padroes = [
        r'gtin[^0-9]{0,20}([0-9]{8,14})',
        r'ean[^0-9]{0,20}([0-9]{8,14})',
        r'barcode[^0-9]{0,20}([0-9]{8,14})',
    ]

    texto = html or ''
    for padrao in padroes:
        achados = re.findall(padrao, texto, flags=re.IGNORECASE)
        if achados:
            return _only_digits(achados[0])

    return ''



def _collect_images(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []

    for meta_prop in ('og:image', 'twitter:image'):
        url = _extract_meta(soup, meta_prop)
        if url:
            urls.append(urljoin(base_url, url))

    for img in soup.find_all('img'):
        candidatos = [
            img.get('src'),
            img.get('data-src'),
            img.get('data-original'),
            img.get('data-lazy'),
            img.get('srcset'),
        ]
        for candidato in candidatos:
            txt = _clean_text(candidato)
            if not txt:
                continue
            if ',' in txt and ' ' in txt:
                txt = txt.split(',')[0].split(' ')[0]
            if txt.startswith('data:image'):
                continue
            absoluto = urljoin(base_url, txt)
            if absoluto not in urls:
                urls.append(absoluto)

    filtradas: List[str] = []
    for url in urls:
        baixa = url.lower()
        if any(token in baixa for token in ('sprite', 'icon', 'logo', 'banner')):
            continue
        if url not in filtradas:
            filtradas.append(url)
    return filtradas[:12]



def _extract_breadcrumb_category(soup: BeautifulSoup) -> str:
    trilhas: List[str] = []

    nav = soup.find(attrs={'aria-label': re.compile('breadcrumb', re.I)})
    if nav:
        trilhas.extend([_clean_text(x.get_text(' ', strip=True)) for x in nav.find_all(['a', 'span', 'li'])])

    if not trilhas:
        for seletor in ['.breadcrumb a', '.breadcrumbs a', '[class*=breadcrumb] a', '[class*=breadcrumbs] a']:
            itens = soup.select(seletor)
            if itens:
                trilhas.extend([_clean_text(x.get_text(' ', strip=True)) for x in itens])
                break

    trilhas = [x for x in trilhas if x and x.lower() not in {'home', 'inicio', 'início'}]
    unicos: List[str] = []
    for item in trilhas:
        if item not in unicos:
            unicos.append(item)
    return ' > '.join(unicos)



def _find_candidate_text(soup: BeautifulSoup, selectors: List[str]) -> str:
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            texto = _clean_text(el.get_text(' ', strip=True))
            if texto:
                return texto
    return ''



def _extract_specs_map(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}

    for row in soup.select('table tr'):
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            chave = _clean_text(cells[0].get_text(' ', strip=True)).lower()
            valor = _clean_text(cells[1].get_text(' ', strip=True))
            if chave and valor and chave not in specs:
                specs[chave] = valor

    for item in soup.select('dl'):
        dts = item.find_all('dt')
        dds = item.find_all('dd')
        for dt, dd in zip(dts, dds):
            chave = _clean_text(dt.get_text(' ', strip=True)).lower()
            valor = _clean_text(dd.get_text(' ', strip=True))
            if chave and valor and chave not in specs:
                specs[chave] = valor

    return specs



def classificar_pagina(html: str, url: str = '') -> Dict[str, object]:
    soup = BeautifulSoup(html or '', 'html.parser')
    texto = (soup.get_text(' ', strip=True) or '').lower()
    json_ld = _parse_json_ld(soup)

    score_produto = 0
    score_categoria = 0
    url_baixa = (url or '').lower()

    if json_ld.get('nome'):
        score_produto += 4
    if json_ld.get('preco'):
        score_produto += 3
    if json_ld.get('gtin'):
        score_produto += 2
    if _extract_meta(soup, 'og:type').lower() == 'product':
        score_produto += 3
    if any(token in url_baixa for token in PRODUCT_URL_HINTS):
        score_produto += 2
    if any(token in texto for token in ('comprar', 'adicionar ao carrinho', 'sku', 'ean', 'gtin')):
        score_produto += 1

    quantidade_links = len(soup.find_all('a', href=True))
    if quantidade_links >= 12:
        score_categoria += 1
    if any(token in url_baixa for token in CATEGORY_URL_HINTS):
        score_categoria += 2
    if any(token in texto for token in ('categorias', 'departamentos', 'coleções', 'colecoes')):
        score_categoria += 2
    if soup.find(attrs={'aria-label': re.compile('breadcrumb', re.I)}):
        score_categoria += 1

    return {
        'is_product': score_produto >= 4 and score_produto >= score_categoria,
        'is_category': score_categoria >= 2 and score_categoria >= score_produto,
        'score_product': score_produto,
        'score_category': score_categoria,
    }



def extrair_produto_html(html: str, url: str) -> Dict:
    soup = BeautifulSoup(html or '', 'html.parser')
    json_ld = _parse_json_ld(soup)
    specs = _extract_specs_map(soup)

    titulo = _pick_first(
        json_ld.get('nome', ''),
        _extract_meta(soup, 'og:title'),
        _find_candidate_text(soup, ['h1', '[class*=product-name]', '[class*=product_title]', '[itemprop=name]']),
        soup.title.get_text(' ', strip=True) if soup.title else '',
    )

    descricao = _pick_first(
        json_ld.get('descricao_curta', ''),
        _extract_meta(soup, 'og:description'),
        _extract_meta(soup, 'description'),
        _find_candidate_text(soup, ['[class*=description]', '[itemprop=description]']),
    )

    imagens_lista = json_ld.get('imagens') or []
    if not isinstance(imagens_lista, list):
        imagens_lista = [_clean_text(imagens_lista)] if _clean_text(imagens_lista) else []
    imagens = imagens_lista or _collect_images(soup, url)

    preco = _pick_first(
        json_ld.get('preco', ''),
        _extract_meta(soup, 'product:price:amount'),
        _extract_meta(soup, 'price'),
        _find_candidate_text(soup, ['[class*=price]', '[data-price]', '[itemprop=price]']),
        _find_price_in_text(html),
    )
    preco = _to_price(preco)

    marca = _pick_first(
        json_ld.get('marca', ''),
        _extract_meta(soup, 'product:brand'),
        specs.get('marca', ''),
        specs.get('brand', ''),
    )

    codigo = _pick_first(
        json_ld.get('codigo', ''),
        specs.get('sku', ''),
        specs.get('código', ''),
        specs.get('codigo', ''),
        specs.get('ref', ''),
        specs.get('referência', ''),
    )

    gtin = _pick_first(
        json_ld.get('gtin', ''),
        specs.get('ean', ''),
        specs.get('gtin', ''),
        specs.get('código de barras', ''),
        _find_gtin_in_text(html),
    )
    gtin = _only_digits(gtin)

    disponibilidade = _pick_first(
        json_ld.get('disponibilidade', ''),
        _extract_meta(soup, 'product:availability'),
        _find_candidate_text(soup, ['[class*=stock]', '[class*=availability]', '[class*=dispon]']),
    )

    categoria = _pick_first(
        json_ld.get('categoria', ''),
        _extract_breadcrumb_category(soup),
    )

    ncm = _pick_first(specs.get('ncm', ''), specs.get('classificação fiscal', ''), specs.get('classificacao fiscal', ''))
    unidade = _pick_first(specs.get('unidade', ''), specs.get('un', ''), specs.get('medida', ''))

    return {
        'origem_tipo': 'scraper_url',
        'origem_arquivo_ou_url': url,
        'codigo': codigo,
        'descricao': titulo,
        'descricao_curta': descricao or titulo,
        'nome': titulo,
        'preco': preco,
        'preco_custo': preco,
        'estoque': '',
        'gtin': gtin,
        'marca': marca,
        'categoria': categoria,
        'ncm': ncm,
        'cest': _pick_first(specs.get('cest', '')),
        'cfop': '',
        'unidade': unidade,
        'fornecedor': '',
        'cnpj_fornecedor': '',
        'imagens': ' | '.join([_clean_text(x) for x in imagens if _clean_text(x)]),
        'disponibilidade_site': disponibilidade,
    }



def extrair_produtos_de_urls(urls: List[str], baixar_html_func) -> pd.DataFrame:
    linhas: List[Dict] = []

    for url in urls:
        resultado = baixar_html_func(url)
        if not resultado.get('ok'):
            linhas.append(
                {
                    'origem_tipo': 'scraper_url',
                    'origem_arquivo_ou_url': url,
                    'codigo': '',
                    'descricao': '',
                    'descricao_curta': '',
                    'nome': '',
                    'preco': '',
                    'preco_custo': '',
                    'estoque': '',
                    'gtin': '',
                    'marca': '',
                    'categoria': '',
                    'ncm': '',
                    'cest': '',
                    'cfop': '',
                    'unidade': '',
                    'fornecedor': '',
                    'cnpj_fornecedor': '',
                    'imagens': '',
                    'disponibilidade_site': '',
                    'erro_scraper': resultado.get('erro', 'Falha ao baixar HTML.'),
                }
            )
            continue

        extraido = extrair_produto_html(resultado.get('html', ''), resultado.get('url', url))
        extraido['erro_scraper'] = ''
        linhas.append(extraido)

    return pd.DataFrame(linhas)
