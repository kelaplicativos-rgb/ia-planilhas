import random
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.logger import log
from core.scraper.fetcher import fetch
from core.utils import limpar, gerar_codigo_fallback, detectar_marca


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

    preco = min(nums)
    if preco <= 0:
        return "0.01"

    return f"{preco:.2f}"


def extrair_imagem(soup, link):
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return urljoin(link, og["content"])

    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return urljoin(link, tw["content"])

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


def extrair_site(link, filtro, estoque_padrao):
    html = fetch(link)
    if not html:
        log(f"HTML vazio para {link}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)

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

    if not produto["Imagem"]:
        produto["Imagem"] = ""

    if not produto["Código"]:
        produto["Código"] = str(random.randint(1000000000000, 9999999999999))

    return produto
