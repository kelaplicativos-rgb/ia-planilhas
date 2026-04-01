import random
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from core.logger import log
from core.utils import limpar, gerar_codigo_fallback, detectar_marca


session = requests.Session()


def get_headers():
    return {
        "User-Agent": random.choice(
            [
                "Mozilla/5.0",
                "Mozilla/5.0 (Windows NT 10.0)",
                "Mozilla/5.0 (Android)",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            ]
        ),
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "keep-alive",
    }


def fetch(url):
    for tentativa in range(3):
        try:
            time.sleep(random.uniform(0.4, 1.0))
            r = session.get(url, headers=get_headers(), timeout=20, verify=False)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
            log(f"WARN fetch status={r.status_code} url={url}")
        except Exception as e:
            log(f"ERRO fetch tentativa={tentativa + 1} url={url} detalhe={e}")
    return None


def extrair_codigo(texto, link):
    padroes = [
        r"C[ÓO]D(?:IGO)?[:\s#-]*([0-9]{6,20})",
        r"SKU[:\s#-]*([0-9A-Z\-_.]{4,30})",
        r"REF(?:ER[EÊ]NCIA)?[:\s#-]*([0-9A-Z\-_.]{4,30})",
        r"\b([0-9]{8,14})\b",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            codigo = limpar(m.group(1))
            if codigo:
                return codigo

    return gerar_codigo_fallback(link)


def extrair_preco(texto):
    valores = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)
    if not valores:
        return "0.01"

    nums = []
    for v in valores:
        try:
            nums.append(float(v.replace(".", "").replace(",", ".")))
        except Exception:
            pass

    if not nums:
        return "0.01"

    # normalmente o menor preço da página é o preço final/promocional
    preco = min(nums)
    if preco <= 0:
        return "0.01"

    return f"{preco:.2f}"


def extrair_imagem(soup, link):
    # prioridade 1: og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return urljoin(link, og["content"])

    # prioridade 2: twitter:image
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return urljoin(link, tw["content"])

    # prioridade 3: imagens do produto
    for img in soup.find_all("img"):
        for attr in ["data-zoom-image", "data-large_image", "data-src", "src"]:
            src = img.get(attr)
            if src and not any(x in src.lower() for x in ["logo", "banner", "icon", "avatar"]):
                return urljoin(link, src)

    return ""


def extrair_descricao_curta_site(soup, nome):
    seletores = [
        ("div", re.compile("descricao|description|product|conteudo|content", re.I)),
        ("section", re.compile("descricao|description|product|conteudo|content", re.I)),
        ("article", re.compile("descricao|description|product|conteudo|content", re.I)),
    ]

    for tag_name, cls_regex in seletores:
        tag = soup.find(tag_name, class_=cls_regex)
        if tag:
            texto = limpar(tag.get_text(" ", strip=True))
            if len(texto) >= 20:
                return texto[:250]

    # fallback: parágrafos úteis
    paragrafos = []
    for p in soup.find_all(["p", "li"]):
        txt = limpar(p.get_text(" ", strip=True))
        if len(txt) >= 30 and not any(
            lixo in txt.lower()
            for lixo in [
                "política",
                "troca",
                "devolução",
                "cookies",
                "atendimento",
                "todos os direitos",
                "formas de pagamento",
                "frete",
            ]
        ):
            paragrafos.append(txt)

    if paragrafos:
        return limpar(" ".join(paragrafos))[:250]

    return nome[:250]


def coletar_links_site(url_base):
    links = []

    for p in range(1, 6):
        html = fetch(f"{url_base}?page={p}")
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # tenta vários padrões de link de produto
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


def extrair_site(link, filtro, estoque_padrao):
    html = fetch(link)
    if not html:
        log(f"HTML vazio para {link}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)

    # nome
    nome = ""
    nome_tag = soup.find("h1")
    if nome_tag:
        nome = limpar(nome_tag.get_text(strip=True))

    if not nome:
        title = soup.find("title")
        if title:
            nome = limpar(title.get_text(strip=True))

    if not nome:
        nome = "Produto sem nome"

    if filtro and filtro.lower() not in nome.lower():
        return None

    # estoque simples
    estoque = estoque_padrao
    texto_lower = texto.lower()
    if any(x in texto_lower for x in ["esgotado", "indisponível", "indisponivel", "sem estoque"]):
        estoque = 0

    produto = {
        "Código": extrair_codigo(texto, link),
        "Produto": nome,
        "Preço": extrair_preco(texto),
        "Descrição Curta": extrair_descricao_curta_site(soup, nome),
        "Imagem": extrair_imagem(soup, link),
        "Link": link,
        "Estoque": estoque,
        "Marca": detectar_marca(nome, texto),
    }

    # fallback final de imagem
    if not produto["Imagem"]:
        produto["Imagem"] = link

    return produto
