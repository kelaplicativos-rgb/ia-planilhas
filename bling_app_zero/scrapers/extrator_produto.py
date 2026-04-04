import json
import re
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = str(value).replace("\xa0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _only_digits(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\D+", "", str(value))


def _to_price(value: Optional[str]) -> str:
    txt = _clean_text(value)
    if not txt:
        return ""

    txt = txt.replace("R$", "").replace(" ", "")
    txt = re.sub(r"[^0-9,.\-]", "", txt)

    if txt.count(",") == 1 and txt.count(".") >= 1:
        txt = txt.replace(".", "").replace(",", ".")
    elif txt.count(",") == 1 and txt.count(".") == 0:
        txt = txt.replace(",", ".")

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
    return ""


def _parse_json_ld(soup: BeautifulSoup) -> Dict:
    produtos: List[Dict] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        blocos = data if isinstance(data, list) else [data]

        for bloco in blocos:
            if not isinstance(bloco, dict):
                continue

            if bloco.get("@type") == "Product":
                produtos.append(bloco)

            grafo = bloco.get("@graph")
            if isinstance(grafo, list):
                for item in grafo:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        produtos.append(item)

    if not produtos:
        return {}

    p = produtos[0]
    offers = p.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}

    brand = p.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name", "")

    images = p.get("image", [])
    if isinstance(images, str):
        images = [images]
    if not isinstance(images, list):
        images = []

    sku = p.get("sku") or p.get("mpn") or ""
    gtin = (
        p.get("gtin13")
        or p.get("gtin12")
        or p.get("gtin14")
        or p.get("gtin8")
        or ""
    )

    return {
        "nome": _clean_text(p.get("name", "")),
        "descricao_curta": _clean_text(p.get("description", "")),
        "marca": _clean_text(brand),
        "codigo": _clean_text(sku),
        "gtin": _only_digits(gtin),
        "preco": _to_price(offers.get("price")),
        "moeda": _clean_text(offers.get("priceCurrency", "")),
        "disponibilidade": _clean_text(offers.get("availability", "")),
        "imagens": " | ".join([_clean_text(x) for x in images if _clean_text(x)]),
    }


def _extract_meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return _clean_text(tag["content"])

    tag = soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return _clean_text(tag["content"])

    return ""


def _find_price_in_text(html: str) -> str:
    padroes = [
        r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}",
        r"R\$\s?\d+,\d{2}",
    ]

    for padrao in padroes:
        achados = re.findall(padrao, html or "", flags=re.IGNORECASE)
        if achados:
            return _to_price(achados[0])

    return ""


def _find_gtin_in_text(html: str) -> str:
    padroes = [
        r"gtin[^0-9]{0,20}([0-9]{8,14})",
        r"ean[^0-9]{0,20}([0-9]{8,14})",
    ]

    texto = html or ""
    for padrao in padroes:
        achados = re.findall(padrao, texto, flags=re.IGNORECASE)
        if achados:
            return _only_digits(achados[0])

    return ""


def extrair_produto_html(html: str, url: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    json_ld = _parse_json_ld(soup)

    titulo = _pick_first(
        json_ld.get("nome", ""),
        _extract_meta(soup, "og:title"),
        soup.title.get_text(" ", strip=True) if soup.title else "",
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "",
    )

    descricao = _pick_first(
        json_ld.get("descricao_curta", ""),
        _extract_meta(soup, "og:description"),
        _extract_meta(soup, "description"),
    )

    imagem = _pick_first(
        json_ld.get("imagens", ""),
        _extract_meta(soup, "og:image"),
    )

    preco = _pick_first(
        json_ld.get("preco", ""),
        _find_price_in_text(html),
    )

    marca = _pick_first(
        json_ld.get("marca", ""),
        _extract_meta(soup, "product:brand"),
    )

    codigo = _pick_first(
        json_ld.get("codigo", ""),
    )

    gtin = _pick_first(
        json_ld.get("gtin", ""),
        _find_gtin_in_text(html),
    )

    disponibilidade = _pick_first(
        json_ld.get("disponibilidade", ""),
    )

    return {
        "origem_tipo": "scraper_url",
        "origem_arquivo_ou_url": url,
        "codigo": codigo,
        "descricao": titulo,
        "descricao_curta": descricao or titulo,
        "nome": titulo,
        "preco": preco,
        "preco_custo": "",
        "estoque": "",
        "gtin": gtin,
        "marca": marca,
        "categoria": "",
        "ncm": "",
        "cest": "",
        "cfop": "",
        "unidade": "",
        "fornecedor": "",
        "cnpj_fornecedor": "",
        "imagens": imagem,
        "disponibilidade_site": disponibilidade,
    }


def extrair_produtos_de_urls(urls: List[str], baixar_html_func) -> pd.DataFrame:
    linhas: List[Dict] = []

    for url in urls:
        resultado = baixar_html_func(url)
        if not resultado.get("ok"):
            linhas.append(
                {
                    "origem_tipo": "scraper_url",
                    "origem_arquivo_ou_url": url,
                    "codigo": "",
                    "descricao": "",
                    "descricao_curta": "",
                    "nome": "",
                    "preco": "",
                    "preco_custo": "",
                    "estoque": "",
                    "gtin": "",
                    "marca": "",
                    "categoria": "",
                    "ncm": "",
                    "cest": "",
                    "cfop": "",
                    "unidade": "",
                    "fornecedor": "",
                    "cnpj_fornecedor": "",
                    "imagens": "",
                    "disponibilidade_site": "",
                    "erro_scraper": resultado.get("erro", "Falha ao baixar HTML."),
                }
            )
            continue

        extraido = extrair_produto_html(resultado.get("html", ""), resultado.get("url", url))
        extraido["erro_scraper"] = ""
        linhas.append(extraido)

    return pd.DataFrame(linhas)
