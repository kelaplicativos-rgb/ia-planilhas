import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import random
import time

def fetch(url):
    try:
        time.sleep(random.uniform(0.5,1.2))
        r = requests.get(url, timeout=15)
        return r.text
    except:
        return None

def coletar_links_site(url_base):
    links = []

    for p in range(1,4):
        html = fetch(f"{url_base}?page={p}")
        if not html:
            continue

        soup = BeautifulSoup(html,"html.parser")

        for a in soup.find_all("a", href=True):
            link = urljoin(url_base,a["href"])
            if "/produto" in link:
                links.append(link)

    return list(set(links))

def extrair_site(link, filtro, estoque_padrao):
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html,"html.parser")
    texto = soup.get_text(" ", strip=True)

    nome = soup.find("h1")
    nome = nome.get_text(strip=True) if nome else "Produto"

    preco = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)

    return {
        "Código": str(random.randint(1000000000000,9999999999999)),
        "Produto": nome,
        "Preço": preco.group() if preco else "1.00",
        "Descrição Curta": nome,
        "Imagem": "",
        "Link": link,
        "Estoque": estoque_padrao,
        "Marca": ""
    }
