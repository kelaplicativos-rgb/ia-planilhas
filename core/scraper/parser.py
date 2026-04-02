import re
from bs4 import BeautifulSoup

from core.ai_product_extractor import extrair_dados_produto_com_ia
from core.logger import log
from core.scraper.fetcher import fetch
from core.utils import (
    detectar_marca,
    gerar_codigo_fallback,
    normalizar_url,
    parse_estoque,
    parse_preco,
)


def _limpar(txt):
    if txt is None:
        return ""
    return " ".join(str(txt).split()).strip()


def extrair_imagem(soup: BeautifulSoup, link: str) -> str:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return normalizar_url(og.get("content"), link)

    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        return normalizar_url(twitter.get("content"), link)

    for img in soup.find_all("img"):
        for attr in ["data-zoom-image", "data-src", "src"]:
            src = img.get(attr)
            if src and not any(bad in src.lower() for bad in ["logo", "banner", "icon"]):
                return normalizar_url(src, link)

    return ""


def extrair_descricao_curta_site(soup: BeautifulSoup, nome: str) -> str:
    seletores = [
        {"name": "div", "class_": re.compile("descricao|description|product|content|detalhe", re.I)},
        {"name": "section", "class_": re.compile("descricao|description|product|content|detalhe", re.I)},
        {"name": "article", "class_": re.compile("descricao|description|product|content|detalhe", re.I)},
    ]

    for sel in seletores:
        tag = soup.find(sel.get("name"), class_=sel.get("class_"))
        if tag:
            texto = _limpar(tag.get_text(" ", strip=True))
            if len(texto) >= 20:
                return texto[:500]

    return (nome or "")[:250]


def extrair_codigo(texto: str, link: str) -> str:
    padroes = [
        r"SKU[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"C[ÓO]D(?:IGO)?[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"REF[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"REFER[ÊE]NCIA[:\s#-]*([A-Z0-9\-_/]{4,40})",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            return str(m.group(1)).strip()

    return gerar_codigo_fallback(link)


def extrair_gtin(texto: str) -> str:
    padroes = [
        r"GTIN[:\s#-]*([0-9]{8,14})",
        r"EAN[:\s#-]*([0-9]{8,14})",
        r"C[ÓO]DIGO DE BARRAS[:\s#-]*([0-9]{8,14})",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            return str(m.group(1)).strip()

    return ""


def extrair_preco(texto: str) -> str:
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

    return f"{min(nums):.2f}"


def _extrair_nome_produto(soup: BeautifulSoup, texto: str) -> str:
    candidatos = []

    h1 = soup.find("h1")
    if h1:
        candidatos.append(_limpar(h1.get_text(" ", strip=True)))

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        candidatos.append(_limpar(og_title.get("content")))

    title = soup.find("title")
    if title:
        candidatos.append(_limpar(title.get_text(" ", strip=True)))

    for nome in candidatos:
        if nome and len(nome) >= 4:
            return nome[:250]

    # fallback bruto
    texto_limpo = _limpar(texto)
    if texto_limpo:
        return texto_limpo[:120]

    return "Produto sem nome"


def _parece_pagina_produto(soup: BeautifulSoup, texto: str, link: str) -> bool:
    lk = (link or "").lower()
    if any(x in lk for x in ["/produto", "/product", "/p/", "-p", ".html"]):
        return True

    txt = (texto or "").lower()

    pistas = [
        "sku",
        "referência",
        "referencia",
        "código",
        "codigo",
        "comprar",
        "adicionar ao carrinho",
        "gtin",
        "ean",
    ]

    score = 0
    for p in pistas:
        if p in txt:
            score += 1

    return score >= 2


def extrair_site(link: str, filtro: str = "", estoque_padrao: int = 0) -> dict | None:
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)
    nome = _extrair_nome_produto(soup, texto)

    if filtro and filtro.lower() not in nome.lower():
        return None

    # não descarta produto por falta de h1
    if not _parece_pagina_produto(soup, texto, link):
        log(f"Página descartada por não parecer produto: {link}")
        return None

    imagem_site = extrair_imagem(soup, link)
    descricao_curta_site = extrair_descricao_curta_site(soup, nome)

    offline = {
        "Código": extrair_codigo(texto, link),
        "GTIN": extrair_gtin(texto),
        "Produto": nome,
        "Preço": extrair_preco(texto),
        "Preço Custo": "",
        "Descrição Curta": descricao_curta_site,
        "Descrição Complementar": descricao_curta_site,
        "Imagem": imagem_site,
        "Link": link,
        "Marca": detectar_marca(nome, texto),
        "Estoque": estoque_padrao,
        "NCM": "",
        "Origem": "0",
        "Peso Líquido": "",
        "Peso Bruto": "",
        "Estoque Mínimo": "",
        "Estoque Máximo": "",
        "Unidade": "UN",
        "Tipo": "Produto",
        "Situação": "Ativo",
    }

    dados_ia = extrair_dados_produto_com_ia(texto_produto=texto, link=link)

    if not dados_ia:
        log(f"Produto extraído via offline: {offline['Produto']}")
        return offline

    codigo_ia = (dados_ia.get("codigo") or "").strip()
    if codigo_ia.lower() == "id":
        codigo_ia = ""

    final = {
        "Código": codigo_ia or offline["Código"],
        "GTIN": dados_ia.get("gtin") or offline["GTIN"],
        "Produto": dados_ia.get("produto") or offline["Produto"],
        "Preço": parse_preco(dados_ia.get("preco") or offline["Preço"]),
        "Preço Custo": parse_preco(dados_ia.get("preco_custo") or offline["Preço Custo"]) if (dados_ia.get("preco_custo") or "").strip() else "",
        "Descrição Curta": dados_ia.get("descricao_curta") or offline["Descrição Curta"],
        "Descrição Complementar": dados_ia.get("descricao_complementar") or offline["Descrição Complementar"],
        "Imagem": normalizar_url(dados_ia.get("imagem") or offline["Imagem"], link),
        "Link": normalizar_url(dados_ia.get("link") or offline["Link"], link),
        "Marca": dados_ia.get("marca") or offline["Marca"],
        "Estoque": parse_estoque(dados_ia.get("estoque") or offline["Estoque"], estoque_padrao),
        "NCM": dados_ia.get("ncm") or offline["NCM"],
        "Origem": dados_ia.get("origem") or offline["Origem"],
        "Peso Líquido": dados_ia.get("peso_liquido") or offline["Peso Líquido"],
        "Peso Bruto": dados_ia.get("peso_bruto") or offline["Peso Bruto"],
        "Estoque Mínimo": dados_ia.get("estoque_minimo") or offline["Estoque Mínimo"],
        "Estoque Máximo": dados_ia.get("estoque_maximo") or offline["Estoque Máximo"],
        "Unidade": dados_ia.get("unidade") or offline["Unidade"],
        "Tipo": dados_ia.get("tipo") or offline["Tipo"],
        "Situação": dados_ia.get("situacao") or offline["Situação"],
    }

    log(f"Produto extraído final: {final['Produto']}")
    return final
