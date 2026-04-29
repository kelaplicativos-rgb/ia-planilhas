# bling_app_zero/core/instant_scraper/ultra_extractor.py

import re
from urllib.parse import urljoin


def extrair_produto(element, base_url):
    text = element.get_text(" ", strip=True)

    nome = ""
    preco = ""
    link = ""
    imagem = ""

    # nome
    for tag in ["h1", "h2", "h3", "a"]:
        el = element.find(tag)
        if el:
            nome = el.get_text(strip=True)
            if len(nome) > 5:
                break

    # preço
    match = re.search(r"R\$\s*\d+[.,]\d{2}", text)
    if match:
        preco = match.group(0)

    # link
    a = element.find("a", href=True)
    if a:
        link = urljoin(base_url, a["href"])

    # imagem
    img = element.find("img")
    if img:
        imagem = img.get("src") or img.get("data-src") or ""

    return {
        "nome": nome,
        "preco": preco,
        "url_produto": link,
        "imagens": imagem,
        "descricao": text[:500]
    }


def extrair_lista(elements, base_url):
    produtos = []

    for el in elements:
        prod = extrair_produto(el, base_url)

        if prod["nome"] and (prod["preco"] or prod["url_produto"]):
            produtos.append(prod)

    return produtos
