import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import random
import time

def fetch(url):
    try:
        time.sleep(random.uniform(0.3,1.0))
        r = requests.get(url, timeout=15)
        return r.text
    except:
        return None

def coletar_links_site(url_base):
    links = []

    for p in range(1,6):
        html = fetch(f"{url_base}?page={p}")
        if not html:
            continue

        soup = BeautifulSoup(html,"html.parser")

        for a in soup.select("a[href*='produto']"):
            link = urljoin(url_base,a["href"])
            links.append(link)

    return list(set(links))


def extrair_site(link, filtro, estoque_padrao):
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html,"html.parser")

    for tag in soup(["script","style","noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)

    nome_tag = soup.find("h1")
    nome = nome_tag.get_text(strip=True) if nome_tag else ""

    if filtro and filtro.lower() not in nome.lower():
        return None

    # PREÇO INTELIGENTE
    precos = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)
    preco = "0.01"
    if precos:
        try:
            preco = str(min([float(p.replace(".","").replace(",", ".")) for p in precos]))
        except:
            pass

    # SKU INTELIGENTE
    codigos = re.findall(r"\b\d{8,14}\b", texto)
    codigo = codigos[0] if codigos else str(random.randint(1000000000000,9999999999999))

    # IMAGEM REAL
    imagem = ""
    og = soup.find("meta", property="og:image")
    if og:
        imagem = og.get("content","")

    # DESCRIÇÃO LIMPA
    descricao = nome

    return {
        "Código": codigo,
        "Produto": nome or "Produto sem nome",
        "Preço": preco,
        "Descrição Curta": descricao,
        "Imagem": imagem,
        "Link": link,
        "Estoque": estoque_padrao,
        "Marca": ""
    }
