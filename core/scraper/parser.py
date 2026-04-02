import json
import re

from bs4 import BeautifulSoup

from core.ai_product_extractor import extrair_dados_produto_com_ia
from core.logger import log
from core.scraper.fetcher import fetch
from core.utils import (
    limpar,
    detectar_marca,
    gerar_codigo_fallback,
    normalizar_url,
    parse_estoque,
    parse_preco,
    validar_gtin,
)

TERMOS_PROPAGANDA_LINK = [
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "wa.me",
    "whatsapp",
    "telegram",
    "tiktok",
    "canal",
    "inscreva-se",
    "promo",
    "cupom",
]


def _link_valido_produto(link: str) -> str:
    link = limpar(link)
    if not link:
        return ""

    lk = link.lower()

    if any(t in lk for t in TERMOS_PROPAGANDA_LINK):
        return ""

    if not (
        lk.startswith("http://")
        or lk.startswith("https://")
        or lk.startswith("www.")
        or "/" in lk
    ):
        return ""

    return link


def _imagem_valida(imagem: str) -> str:
    imagem = limpar(imagem)
    if not imagem:
        return ""

    lk = imagem.lower()
    if any(t in lk for t in TERMOS_PROPAGANDA_LINK):
        return ""

    return imagem


def extrair_imagem(soup: BeautifulSoup, link: str) -> str:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img = _imagem_valida(og.get("content"))
        if img:
            return normalizar_url(img, link)

    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        img = _imagem_valida(twitter.get("content"))
        if img:
            return normalizar_url(img, link)

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
                if "image" in obj:
                    img = obj["image"]
                    if isinstance(img, str):
                        return img
                    if isinstance(img, list) and img and isinstance(img[0], str):
                        return img[0]

                for _, v in obj.items():
                    achado = walk(v)
                    if achado:
                        return achado

            elif isinstance(obj, list):
                for item in obj:
                    achado = walk(item)
                    if achado:
                        return achado

            return ""

        achado = walk(dado)
        achado = _imagem_valida(achado)
        if achado:
            return normalizar_url(achado, link)

    for img in soup.find_all("img"):
        for attr in ["data-zoom-image", "data-src", "src"]:
            src = img.get(attr)
            if src and not any(bad in src.lower() for bad in ["logo", "banner", "icon"]):
                src = _imagem_valida(src)
                if src:
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
            texto = limpar(tag.get_text(" ", strip=True))
            if len(texto) >= 20:
                return texto[:250]

    return (nome or "")[:180]


def extrair_codigo(texto: str, link: str) -> str:
    padroes = [
        r"SKU[:\s#-]*([A-Z0-9\-_\/]{2,40})",
        r"C[ÓO]D(?:IGO)?[:\s#-]*([A-Z0-9\-_\/]{2,40})",
        r"REF[:\s#-]*([A-Z0-9\-_\/]{2,40})",
        r"REFER[ÊE]NCIA[:\s#-]*([A-Z0-9\-_\/]{2,40})",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            valor = limpar(m.group(1))
            if valor and valor.lower() != "id":
                return valor

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
            return validar_gtin(m.group(1))

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
        candidatos.append(limpar(h1.get_text(" ", strip=True)))

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        candidatos.append(limpar(og_title.get("content")))

    title = soup.find("title")
    if title:
        candidatos.append(limpar(title.get_text(" ", strip=True)))

    for nome in candidatos:
        if nome and len(nome) >= 4:
            return nome[:220]

    return limpar(texto[:120]) or "Produto sem nome"


def _parece_pagina_produto(soup: BeautifulSoup, texto: str, link: str) -> bool:
    lk = (link or "").lower()
    if any(x in lk for x in ["/produto", "/product", "/p/", "-p", ".html"]):
        return True

    txt = (texto or "").lower()
    pistas = ["sku", "referência", "codigo", "comprar", "ean", "preço", "preco"]

    score = 0
    for p in pistas:
        if p in txt:
            score += 1

    return score >= 2


def _offline_produto(soup: BeautifulSoup, texto: str, nome: str, link: str, estoque_padrao: int) -> dict:
    imagem_site = extrair_imagem(soup, link)
    descricao_curta_site = extrair_descricao_curta_site(soup, nome)

    link_limpo = _link_valido_produto(link)
    link_limpo = normalizar_url(link_limpo, link) if link_limpo else ""

    return {
        "Código": extrair_codigo(texto, link),
        "GTIN": extrair_gtin(texto),
        "Produto": nome,
        "Preço": extrair_preco(texto),
        "Preço Custo": "",
        "Descrição Curta": descricao_curta_site,
        "Descrição Complementar": "",
        "Imagem": imagem_site,
        "Link": link_limpo,
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


def _precisa_ia(offline: dict) -> bool:
    faltando = 0

    for campo in ["Produto", "Descrição Curta", "Marca"]:
        if not limpar(offline.get(campo, "")):
            faltando += 1

    return faltando >= 1


def extrair_site(link: str, filtro: str = "", estoque_padrao: int = 0) -> dict | None:
    html = fetch(link)
    if not html:
        log(f"Falha ao abrir produto: {link}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        if tag.name != "script" or tag.get("type") != "application/ld+json":
            tag.decompose()

    texto = soup.get_text(" ", strip=True)
    nome = _extrair_nome_produto(soup, texto)

    if filtro and filtro.lower() not in nome.lower():
        return None

    if not _parece_pagina_produto(soup, texto, link):
        return None

    offline = _offline_produto(soup, texto, nome, link, estoque_padrao)

    if not _precisa_ia(offline):
        log(f"Produto extraído offline: {offline['Produto']}")
        return offline

    dados_ia = extrair_dados_produto_com_ia(texto_produto=texto, link=link)

    if not dados_ia:
        log(f"Produto extraído via offline fallback: {offline['Produto']}")
        return offline

    codigo_ia = limpar(dados_ia.get("codigo", ""))
    gtin_ia = validar_gtin(dados_ia.get("gtin", ""))
    marca_ia = limpar(dados_ia.get("marca", ""))

    final = {
        "Código": codigo_ia or offline["Código"],
        "GTIN": gtin_ia or offline["GTIN"],
        "Produto": limpar(dados_ia.get("produto", "")) or offline["Produto"],
        "Preço": parse_preco(dados_ia.get("preco") or offline["Preço"]),
        "Preço Custo": "",
        "Descrição Curta": limpar(dados_ia.get("descricao_curta", "")) or offline["Descrição Curta"],
        "Descrição Complementar": "",
        "Imagem": offline["Imagem"],
        "Link": offline["Link"],
        "Marca": marca_ia or offline["Marca"],
        "Estoque": parse_estoque(dados_ia.get("estoque") or offline["Estoque"], estoque_padrao),
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

    if not final["Código"]:
        final["Código"] = offline["Código"] or gerar_codigo_fallback(final["Link"] or final["Produto"])

    if not final["Descrição Curta"]:
        final["Descrição Curta"] = final["Produto"]

    if not final["Marca"]:
        final["Marca"] = detectar_marca(final["Produto"], final["Descrição Curta"])

    log(f"Produto extraído final: {final['Produto']}")
    return final
