import re
from bs4 import BeautifulSoup

from core.ai_product_extractor import extrair_dados_produto_com_ia
from core.logger import log
from core.scraper.fetcher import fetch
from core.utils import (
    detectar_marca,
    gerar_codigo_fallback,
    normalizar_url,
    parse_preco,
    parse_estoque,
)


def extrair_imagem(soup: BeautifulSoup, link: str) -> str:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return normalizar_url(og.get("content"), link)

    for img in soup.find_all("img"):
        for attr in ["data-zoom-image", "data-src", "src"]:
            src = img.get(attr)
            if src and not any(bad in src.lower() for bad in ["logo", "banner", "icon"]):
                return normalizar_url(src, link)

    return ""


def extrair_descricao_curta_site(soup: BeautifulSoup, nome: str) -> str:
    seletores = [
        {"name": "div", "class_": re.compile("descricao|description|product", re.I)},
        {"name": "section", "class_": re.compile("descricao|description|product", re.I)},
        {"name": "article", "class_": re.compile("descricao|description|product", re.I)},
    ]

    for sel in seletores:
        tag = soup.find(sel.get("name"), class_=sel.get("class_"))
        if tag:
            texto = " ".join(tag.get_text(" ", strip=True).split())
            if len(texto) >= 20:
                return texto[:500]

    return (nome or "")[:250]


def extrair_codigo(texto: str, link: str) -> str:
    padroes = [
        r"C[ÓO]D[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"SKU[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"REF[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"REFER[ÊE]NCIA[:\s#-]*([A-Z0-9\-_/]{4,40})",
        r"\b([0-9]{8,14})\b",
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
        r"\b([0-9]{8,14})\b",
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

    preco = min(nums)
    return f"{preco:.2f}"


def extrair_site(link: str, filtro: str = "", estoque_padrao: int = 0) -> dict | None:
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)
    nome_tag = soup.find("h1")
    nome = nome_tag.get_text(strip=True) if nome_tag else "Produto sem nome"

    if filtro and filtro.lower() not in nome.lower():
        return None

    # =========================
    # BASE OFFLINE
    # =========================
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

    # =========================
    # IA
    # =========================
    dados_ia = extrair_dados_produto_com_ia(texto_produto=texto, link=link)

    if not dados_ia:
        return offline

    final = {
        "Código": dados_ia.get("codigo") or offline["Código"],
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

    log(f"Produto extraído final: {final}")
    return final
