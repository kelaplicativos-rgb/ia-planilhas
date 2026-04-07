from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ==========================================================
# IMPORTS OPCIONAIS (BLINDAGEM)
# ==========================================================
try:
    from bling_app_zero.core.fornecedores_adaptativos import (
        carregar_fornecedor,
        extrair_dominio,
        garantir_fornecedor_adaptativo,
    )
except Exception:
    def carregar_fornecedor(_dominio: str):
        return None

    def extrair_dominio(url: str) -> str:
        try:
            return urlparse(str(url or "").strip()).netloc.lower().replace("www.", "")
        except Exception:
            return ""

    def garantir_fornecedor_adaptativo(_url: str, _html: str | None = None) -> None:
        return None


# ==========================================================
# CONFIG
# ==========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

MAX_THREADS = 10
TIMEOUT = 20
MAX_RETRIES = 3
MAX_LINKS = 400
MAX_PAGINAS = 12


# ==========================================================
# FETCH ROBUSTO
# ==========================================================
def _fetch(url: str) -> str | None:
    url = str(url or "").strip()
    if not url:
        return None

    session = requests.Session()

    for tentativa in range(MAX_RETRIES):
        try:
            response = session.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code == 200:
                response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                return response.text
        except Exception:
            pass

        time.sleep(0.8 + tentativa * 0.6)

    return None


# ==========================================================
# HELPERS
# ==========================================================
def _texto_limpo(valor: str) -> str:
    texto = unescape(str(valor or ""))
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _slug(texto: str) -> str:
    texto = _texto_limpo(texto).lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _texto(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                texto = el.get_text(" ", strip=True)
                if texto:
                    return _texto_limpo(texto)
        except Exception:
            continue
    return ""


def _atributo(soup: BeautifulSoup, selectors: list[str], attr: str) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                valor = el.get(attr)
                if valor:
                    return _texto_limpo(valor)
        except Exception:
            continue
    return ""


def _meta_content(soup: BeautifulSoup, propriedades: list[str], attr: str = "property") -> str:
    for prop in propriedades:
        try:
            el = soup.find("meta", attrs={attr: prop})
            if el and el.get("content"):
                return _texto_limpo(el.get("content"))
        except Exception:
            continue
    return ""


def _normalizar_preco(valor: str) -> str:
    texto = _texto_limpo(valor)
    if not texto:
        return ""

    match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})|\d+(?:\.\d{2}))", texto)
    if match:
        return match.group(1).strip()

    texto = texto.replace("R$", "").replace("r$", "").strip()
    return texto


def _preco_para_float(valor: str) -> float:
    texto = _normalizar_preco(valor)
    if not texto:
        return 0.0

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^\d\.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def _mesmo_dominio(base_url: str, link: str) -> bool:
    try:
        base_host = urlparse(base_url).netloc.lower().replace("www.", "")
        link_host = urlparse(link).netloc.lower().replace("www.", "")
        return bool(base_host and link_host and base_host == link_host)
    except Exception:
        return False


def _url_valida(link: str) -> bool:
    return str(link or "").lower().startswith(("http://", "https://"))


def _normalizar_link(base_url: str, href: str) -> str:
    href = _texto_limpo(href)
    if not href:
        return ""

    link = urljoin(base_url, href)

    if not _url_valida(link):
        return ""

    return link.split("#")[0].strip()


def _parece_link_irrelevante(link: str) -> bool:
    link_lower = str(link or "").lower()

    bloqueados = [
        "javascript:",
        "mailto:",
        "tel:",
        "whatsapp:",
        "/cart",
        "/carrinho",
        "/checkout",
        "/login",
        "/conta",
        "/account",
        "/customer",
        "/search",
        "/buscar?",
        "/busca?",
        "/wp-content/",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".pdf",
    ]
    return any(item in link_lower for item in bloqueados)


def _coletar_json_ld(soup: BeautifulSoup) -> list[dict]:
    itens: list[dict] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = script.string or script.get_text(" ", strip=True) or ""
        bruto = bruto.strip()
        if not bruto:
            continue

        try:
            data = json.loads(bruto)
        except Exception:
            continue

        if isinstance(data, dict):
            itens.append(data)
        elif isinstance(data, list):
            itens.extend([x for x in data if isinstance(x, dict)])

    return itens


def _percorrer_json_ld(obj):
    if isinstance(obj, dict):
        yield obj
        for valor in obj.values():
            yield from _percorrer_json_ld(valor)
    elif isinstance(obj, list):
        for item in obj:
            yield from _percorrer_json_ld(item)


def _extrair_produto_json_ld(soup: BeautifulSoup, url: str) -> dict:
    for bloco in _coletar_json_ld(soup):
        for item in _percorrer_json_ld(bloco):
            tipo = item.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]

            tipos_norm = {_slug(str(t)) for t in tipos if t}
            if "product" not in tipos_norm:
                continue

            nome = _texto_limpo(item.get("name"))
            descricao = _texto_limpo(item.get("description"))

            imagem = ""
            img = item.get("image")
            if isinstance(img, str):
                imagem = _normalizar_link(url, img)
            elif isinstance(img, list) and img:
                imagem = _normalizar_link(url, str(img[0]))

            preco = ""
            disponibilidade = ""

            offers = item.get("offers")
            offers_list = offers if isinstance(offers, list) else [offers]

            for offer in offers_list:
                if not isinstance(offer, dict):
                    continue

                preco = _texto_limpo(
                    offer.get("price")
                    or offer.get("lowPrice")
                    or offer.get("highPrice")
                )
                disponibilidade = _texto_limpo(offer.get("availability"))
                if preco:
                    break

            estoque = 0
            disp_slug = _slug(disponibilidade)
            if "instock" in disp_slug or "in stock" in disp_slug:
                estoque = 10
            elif "outofstock" in disp_slug or "out of stock" in disp_slug:
                estoque = 0

            if nome:
                return {
                    "Nome": nome,
                    "Preço": _normalizar_preco(preco),
                    "Descrição": descricao,
                    "Imagem": imagem,
                    "Link": url,
                    "Estoque": estoque,
                }

    return {}


def _detectar_estoque(html: str, soup: BeautifulSoup) -> int:
    texto_html = str(html or "").lower()
    texto_pagina = soup.get_text(" ", strip=True).lower()

    termos_sem_estoque = [
        "esgotado",
        "indisponível",
        "indisponivel",
        "sem estoque",
        "out of stock",
        "sold out",
        "produto indisponivel",
        "produto indisponível",
    ]
    if any(t in texto_html or t in texto_pagina for t in termos_sem_estoque):
        return 0

    termos_com_estoque = [
        "comprar",
        "adicionar ao carrinho",
        "adicionar à sacola",
        "disponível",
        "disponivel",
        "em estoque",
        "buy now",
        "in stock",
    ]
    if any(t in texto_html or t in texto_pagina for t in termos_com_estoque):
        return 10

    return 0


def _extrair_nome_produto_generico(soup: BeautifulSoup) -> str:
    candidatos = [
        _meta_content(soup, ["og:title"]),
        _texto(
            soup,
            [
                "h1",
                "h1.product_title",
                ".product-title",
                ".product-name",
                ".produto_nome",
                ".product_title",
                "[itemprop='name']",
                "[class*='product-title']",
                "[class*='product-name']",
                "[class*='produto'] h1",
            ],
        ),
    ]

    for nome in candidatos:
        nome = _texto_limpo(nome)
        if nome and len(nome) >= 3:
            return nome

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return _texto_limpo(title)


def _extrair_preco_produto_generico(soup: BeautifulSoup) -> str:
    candidatos = [
        _meta_content(soup, ["product:price:amount"]),
        _meta_content(soup, ["og:price:amount"]),
        _atributo(
            soup,
            [
                "[itemprop='price']",
                "meta[itemprop='price']",
                "meta[property='product:price:amount']",
            ],
            "content",
        ),
        _texto(
            soup,
            [
                ".price",
                ".valor",
                ".product-price",
                ".price-current",
                ".special-price",
                ".final-price",
                ".woocommerce-Price-amount",
                "[class*='price']",
                "[class*='valor']",
                "[class*='preco']",
                "[class*='pricing']",
            ],
        ),
    ]

    melhor = ""
    melhor_float = 0.0

    for candidato in candidatos:
        candidato = _normalizar_preco(candidato)
        valor = _preco_para_float(candidato)
        if valor > melhor_float:
            melhor_float = valor
            melhor = candidato

    return melhor


def _extrair_descricao_produto_generica(soup: BeautifulSoup) -> str:
    candidatos = [
        _meta_content(soup, ["og:description"]),
        _meta_content(soup, ["description"], attr="name"),
        _texto(
            soup,
            [
                ".description",
                ".product-description",
                ".woocommerce-product-details__short-description",
                "[itemprop='description']",
                "[class*='description']",
                "[class*='descricao']",
                ".tab-description",
                "#description",
            ],
        ),
    ]

    for descricao in candidatos:
        descricao = _texto_limpo(descricao)
        if descricao and len(descricao) >= 10:
            return descricao

    return ""


def _extrair_imagens_produto_genericas(soup: BeautifulSoup, url: str) -> str:
    imagens: list[str] = []
    vistos = set()

    candidatos = [
        _meta_content(soup, ["og:image"]),
        _meta_content(soup, ["twitter:image"], attr="name"),
        _atributo(soup, ["img[data-zoom-image]"], "data-zoom-image"),
        _atributo(soup, ["img[data-large_image]"], "data-large_image"),
        _atributo(
            soup,
            [
                ".product-gallery img",
                ".woocommerce-product-gallery img",
                ".product img",
                "[class*='gallery'] img",
                "[class*='product'] img",
                "img",
            ],
            "src",
        ),
    ]

    for img in candidatos:
        img = _normalizar_link(url, img)
        if not img:
            continue
        if img.lower() in vistos:
            continue
        vistos.add(img.lower())
        imagens.append(img)

    for img_tag in soup.select(
        ".product-gallery img, "
        ".woocommerce-product-gallery img, "
        "[class*='gallery'] img, "
        "[class*='thumb'] img, "
        "[class*='product'] img"
    ):
        try:
            candidato = (
                img_tag.get("data-zoom-image")
                or img_tag.get("data-large_image")
                or img_tag.get("data-src")
                or img_tag.get("src")
                or ""
            )
            candidato = _normalizar_link(url, candidato)
            if not candidato:
                continue
            if candidato.lower() in vistos:
                continue
            vistos.add(candidato.lower())
            imagens.append(candidato)
        except Exception:
            continue

        if len(imagens) >= 10:
            break

    return "|".join(imagens)


def _score_link_produto(link: str, texto_ancora: str = "", classes: str = "") -> float:
    link_slug = _slug(link)
    texto_slug = _slug(texto_ancora)
    classes_slug = _slug(classes)

    score = 0.0

    sinais_fortes = [
        "produto",
        "product",
        "item",
        "p/",
        "/p/",
        "/produto/",
        "/product/",
        "/prod/",
        "sku",
    ]
    for sinal in sinais_fortes:
        if sinal in link.lower():
            score += 3.0

    sinais_medios = [
        "buy",
        "comprar",
        "detalhe",
        "details",
        "shop",
        "loja",
        "catalog",
        "catalogo",
        "colecao",
        "coleção",
    ]
    for sinal in sinais_medios:
        if sinal in link_slug or sinal in texto_slug or sinal in classes_slug:
            score += 1.0

    if re.search(r"/[a-z0-9\-]+-\d{3,}", link.lower()):
        score += 1.5

    if texto_ancora and len(texto_ancora.strip()) >= 6:
        score += 0.5

    return score


def _parece_pagina_produto(html: str, url: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    if _extrair_produto_json_ld(soup, url).get("Nome"):
        return True

    nome = _extrair_nome_produto_generico(soup)
    preco = _extrair_preco_produto_generico(soup)

    if nome and _preco_para_float(preco) > 0:
        return True

    texto = soup.get_text(" ", strip=True).lower()
    if "adicionar ao carrinho" in texto or "comprar" in texto:
        if nome:
            return True

    return False


# ==========================================================
# ADAPTADOR POR FORNECEDOR
# ==========================================================
def _garantir_lista(valor) -> list[str]:
    if isinstance(valor, list):
        return [str(v).strip() for v in valor if str(v).strip()]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


def _extrair_com_seletores_texto(soup: BeautifulSoup, seletores: list[str]) -> str:
    for sel in _garantir_lista(seletores):
        try:
            el = soup.select_one(sel)
            if not el:
                continue

            if el.name == "meta":
                val = _texto_limpo(el.get("content"))
            else:
                val = _texto_limpo(el.get_text(" ", strip=True))

            if val:
                return val
        except Exception:
            continue
    return ""


def _extrair_imagens_com_config(
    soup: BeautifulSoup,
    base_url: str,
    seletores: list[str],
    imagens_multiplas: bool,
) -> str:
    imagens: list[str] = []
    vistos = set()

    if not seletores:
        return ""

    for sel in _garantir_lista(seletores):
        try:
            elementos = soup.select(sel)
        except Exception:
            continue

        for el in elementos:
            try:
                candidatos = [
                    el.get("content"),
                    el.get("data-zoom-image"),
                    el.get("data-large_image"),
                    el.get("data-src"),
                    el.get("src"),
                ]

                for candidato in candidatos:
                    link = _normalizar_link(base_url, candidato)
                    if not link:
                        continue

                    chave = link.lower()
                    if chave in vistos:
                        continue

                    vistos.add(chave)
                    imagens.append(link)

                    if not imagens_multiplas:
                        return link

                    if len(imagens) >= 10:
                        return "|".join(imagens)
            except Exception:
                continue

    return "|".join(imagens)


def _extrair_produto_por_fornecedor(html: str, url: str, config: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    seletores = config.get("seletores", {}) if isinstance(config.get("seletores", {}), dict) else {}

    nome = _extrair_com_seletores_texto(soup, seletores.get("nome", []))
    preco = _extrair_com_seletores_texto(soup, seletores.get("preco", []))
    descricao = _extrair_com_seletores_texto(soup, seletores.get("descricao", []))
    imagem = _extrair_imagens_com_config(
        soup,
        url,
        seletores.get("imagem", []),
        bool(config.get("imagens_multiplas", True)),
    )

    if not nome:
        nome = _extrair_nome_produto_generico(soup)
    if not preco:
        preco = _extrair_preco_produto_generico(soup)
    if not descricao:
        descricao = _extrair_descricao_produto_generica(soup)
    if not imagem:
        imagem = _extrair_imagens_produto_genericas(soup, url)

    estoque = _detectar_estoque(html, soup)

    return {
        "Nome": _texto_limpo(nome),
        "Preço": _normalizar_preco(preco),
        "Descrição": _texto_limpo(descricao),
        "Imagem": imagem,
        "Link": url,
        "Estoque": estoque,
    }


# ==========================================================
# EXTRAÇÃO DE PRODUTO
# ==========================================================
def _extrair_produto(html: str, url: str) -> dict:
    dominio = extrair_dominio(url)
    config_fornecedor = carregar_fornecedor(dominio)

    if config_fornecedor:
        produto = _extrair_produto_por_fornecedor(html, url, config_fornecedor)
        if produto.get("Nome"):
            return produto

    soup = BeautifulSoup(html, "html.parser")

    try:
        garantir_fornecedor_adaptativo(url, html)
    except Exception:
        pass

    produto_json = _extrair_produto_json_ld(soup, url)

    nome = produto_json.get("Nome", "") or _extrair_nome_produto_generico(soup)
    preco = produto_json.get("Preço", "") or _extrair_pre
