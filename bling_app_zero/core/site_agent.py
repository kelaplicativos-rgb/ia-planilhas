from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

FORNECEDORES_DEDICADOS = {
    "megacentereletronicos.com.br": {
        "produto_hints": [
            "/produto",
            "/product",
            "/p/",
            "/item/",
            "/sku/",
        ],
        "categoria_hints": [
            "/categoria",
            "/collections/",
            "/colecao/",
            "/departamento/",
            "/busca",
            "/search",
        ],
        "title_selectors": [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
        ],
        "price_selectors": [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
        ],
        "image_selectors": [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    },
    "atacadum.com.br": {
        "produto_hints": [
            "/produto",
            "/product",
            "/p/",
            "/item/",
            "/sku/",
        ],
        "categoria_hints": [
            "/categoria",
            "/collections/",
            "/colecao/",
            "/departamento/",
            "/busca",
            "/search",
        ],
        "title_selectors": [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
        ],
        "price_selectors": [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
        ],
        "image_selectors": [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    },
}

STOP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".css",
    ".js",
    ".xml",
    ".json",
)

ROTAS_INICIAIS_PADRAO = (
    "/",
    "/produtos",
    "/produto",
    "/categorias",
    "/categoria",
    "/departamentos",
    "/collections",
    "/colecoes",
    "/shop",
    "/loja",
    "/busca",
    "/search",
)


def _safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip()
    except Exception:
        return ""


def _normalizar_texto(valor: Any) -> str:
    return _safe_str(valor).lower()


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_dominio(base_url: str, url: str) -> bool:
    return _dominio(base_url) == _dominio(url)


def _fornecedor_cfg(base_url: str) -> dict:
    return FORNECEDORES_DEDICADOS.get(_dominio(base_url), {})


def _get_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    return sess


def _fetch_html_retry(
    url: str,
    timeout: int = 20,
    tentativas: int = 3,
    backoff: float = 1.2,
) -> str:
    sess = _get_session()
    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            resp = sess.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                time.sleep(backoff * tentativa)

    raise ultimo_erro if ultimo_erro else RuntimeError("Falha ao buscar HTML")


def _url_valida_para_crawl(base_url: str, url: str) -> bool:
    url = _safe_str(url)
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    if not _mesmo_dominio(base_url, url):
        return False

    url_l = url.lower()
    if any(ext in url_l for ext in STOP_EXTENSIONS):
        return False

    if url_l.startswith(("mailto:", "tel:", "javascript:", "#")):
        return False

    return True


def _normalizar_link_crawl(base_url: str, href: str) -> str:
    href = _safe_str(href)
    if not href:
        return ""

    url = urljoin(base_url, href)
    url = url.split("#")[0].strip()

    if "?" in url:
        base, query = url.split("?", 1)
        params_filtrados = []
        for param in query.split("&"):
            p = param.strip()
            if not p:
                continue
            p_l = p.lower()
            if p_l.startswith(
                (
                    "utm_",
                    "fbclid=",
                    "gclid=",
                    "sort=",
                    "order=",
                    "dir=",
                    "variant=",
                    "view=",
                )
            ):
                continue
            params_filtrados.append(p)

        query = "&".join(params_filtrados).strip("&")
        url = f"{base}?{query}" if query else base

    return url.rstrip("/")


def _extrair_preco(texto: str) -> str:
    texto = _safe_str(texto)
    if not texto:
        return ""

    match = re.search(r"R\$\s*\d[\d\.\,]*", texto, flags=re.I)
    if match:
        return match.group(0).strip()

    match = re.search(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b", texto)
    if match:
        return match.group(0).strip()

    return ""


def _normalizar_preco_para_planilha(valor: str) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        numero = float(texto)
        return f"{numero:.2f}".replace(".", ",")
    except Exception:
        return ""


def _normalizar_imagens(valor: Any) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace("\r", "|").replace(";", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]

    vistos = set()
    urls = []
    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)

    return "|".join(urls)


def _texto_por_selectors(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                if el.name == "meta":
                    content = _safe_str(el.get("content"))
                    if content:
                        return content
                txt = _safe_str(el.get_text(" ", strip=True))
                if txt:
                    return txt
        except Exception:
            continue
    return ""


def _imagens_por_selectors(url_produto: str, soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    imagens = []
    vistos = set()

    for selector in selectors:
        try:
            for el in soup.select(selector):
                src = _safe_str(
                    el.get("content")
                    or el.get("src")
                    or el.get("data-src")
                    or el.get("data-zoom-image")
                )
                if not src:
                    continue

                url_img = urljoin(url_produto, src)
                if url_img in vistos:
                    continue

                vistos.add(url_img)
                imagens.append(url_img)
        except Exception:
            continue

    return imagens


def _classificar_link(base_url: str, url: str, texto_ancora: str = "", bloco: str = "") -> str:
    cfg = _fornecedor_cfg(base_url)
    url_n = _normalizar_texto(url)
    texto_n = _normalizar_texto(texto_ancora)
    bloco_n = _normalizar_texto(bloco)

    hints_produto = cfg.get(
        "produto_hints",
        ["/produto", "/product", "/p/", "/item/", "/sku/", "/prd/"],
    )
    hints_categoria = cfg.get(
        "categoria_hints",
        ["/categoria", "/categorias", "/collections/", "/departamento", "/busca", "/search"],
    )

    score_produto = 0
    score_categoria = 0

    if any(h in url_n for h in hints_produto):
        score_produto += 4

    if any(h in url_n for h in hints_categoria):
        score_categoria += 4

    if re.search(r"/p/\d+|/produto/|/product/|/sku/|/item/", url_n):
        score_produto += 3

    if re.search(r"/categoria/|/categorias/|/collections?/|/departamentos?/", url_n):
        score_categoria += 3

    if any(t in texto_n for t in ["comprar", "ver produto", "detalhes", "sku", "código"]):
        score_produto += 2

    if any(t in texto_n for t in ["categoria", "departamento", "coleção", "produtos"]):
        score_categoria += 2

    if _extrair_preco(bloco_n):
        score_produto += 1

    if any(t in bloco_n for t in ["adicionar ao carrinho", "comprar agora"]):
        score_produto += 1

    if "page=" in url_n or "/page/" in url_n:
        score_categoria += 2

    if score_produto >= max(3, score_categoria):
        return "produto"

    if score_categoria >= 2:
        return "categoria"

    return "indefinido"


def _extrair_links_pagina(base_url: str, url_pagina: str, html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")

    links_categoria = []
    links_produto = []
    vistos_categoria = set()
    vistos_produto = set()

    for a in soup.find_all("a", href=True):
        href = _safe_str(a.get("href"))
        if not href:
            continue

        url = _normalizar_link_crawl(base_url, href)
        if not _url_valida_para_crawl(base_url, url):
            continue

        texto = " ".join(a.stripped_strings).strip()
        bloco = ""
        try:
            bloco = a.parent.get_text(" ", strip=True)[:800]
        except Exception:
            bloco = texto

        classe = _classificar_link(base_url, url, texto, bloco)

        if classe == "produto":
            if url not in vistos_produto:
                vistos_produto.add(url)
                links_produto.append(url)
            continue

        if classe == "categoria":
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)
            continue

        if _url_valida_para_crawl(base_url, url):
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)

    if url_pagina not in vistos_categoria and _classificar_link(base_url, url_pagina) == "categoria":
        links_categoria.insert(0, url_pagina)

    return links_categoria, links_produto


def _rotas_iniciais(base_url: str, termo: str = "") -> list[str]:
    base = _normalizar_url(base_url)
    urls = [f"{base}{rota}" for rota in ROTAS_INICIAIS_PADRAO]

    termo = _safe_str(termo)
    if termo:
        q = quote_plus(termo)
        slug = re.sub(r"[^a-z0-9]+", "-", _normalizar_texto(termo)).strip("-")
        urls.extend(
            [
                f"{base}/search?q={q}",
                f"{base}/busca?q={q}",
                f"{base}/busca?search={q}",
                f"{base}/catalogsearch/result/?q={q}",
                f"{base}/categoria/{slug}",
                f"{base}/?s={q}",
            ]
        )

    vistos = set()
    saida = []
    for url in urls:
        url = _normalizar_link_crawl(base, url)
        if url and url not in vistos:
            vistos.add(url)
            saida.append(url)

    return saida


def _extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    cfg = _fornecedor_cfg(url_produto)

    title_selectors = cfg.get(
        "title_selectors",
        [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
            "meta[property='og:title']",
            "title",
        ],
    )

    price_selectors = cfg.get(
        "price_selectors",
        [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
            "meta[property='product:price:amount']",
        ],
    )

    image_selectors = cfg.get(
        "image_selectors",
        [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    )

    titulo = _texto_por_selectors(soup, title_selectors)
    texto_total = soup.get_text(" ", strip=True)

    preco = _texto_por_selectors(soup, price_selectors)
    if not preco:
        preco = _extrair_preco(texto_total)

    imagens = _imagens_por_selectors(url_produto, soup, image_selectors)
    if not imagens:
        for img in soup.find_all("img"):
            src = _safe_str(img.get("src") or img.get("data-src"))
            if not src:
                continue
            url_img = urljoin(url_produto, src)
            if _mesmo_dominio(url_produto, url_img):
                imagens.append(url_img)
            if len(imagens) >= 8:
                break

    codigo = ""
    gtin = ""
    ncm = ""

    padroes_codigo = [
        r"(?:sku|c[oó]d(?:igo)?|refer[eê]ncia)[\s:\-#]*([A-Za-z0-9\-_\.\/]+)",
    ]
    padroes_gtin = [
        r"(?:gtin|ean|c[oó]digo de barras)[\s:\-#]*([0-9]{8,14})",
    ]
    padroes_ncm = [
        r"(?:ncm)[\s:\-#]*([0-9\.]{6,10})",
    ]

    for padrao in padroes_codigo:
        m = re.search(padrao, texto_total, flags=re.I)
        if m:
            codigo = _safe_str(m.group(1))
            break

    for padrao in padroes_gtin:
        m = re.search(padrao, texto_total, flags=re.I)
        if m:
            gtin = _safe_str(m.group(1))
            break

    for padrao in padroes_ncm:
        m = re.search(padrao, texto_total, flags=re.I)
        if m:
            ncm = _safe_str(m.group(1))
            break

    categoria = ""
    breadcrumb = []
    for el in soup.select("nav a, .breadcrumb a, [class*=breadcrumb] a"):
        txt = _safe_str(el.get_text(" ", strip=True))
        if txt:
            breadcrumb.append(txt)

    if breadcrumb:
        categoria = " > ".join(breadcrumb)

    estoque = ""
    texto_total_n = texto_total.lower()
    if any(x in texto_total_n for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
        estoque = "0"

    return {
        "url_produto": url_produto,
        "codigo": codigo,
        "descricao": titulo,
        "categoria": categoria,
        "gtin": gtin,
        "ncm": ncm,
        "preco": _normalizar_preco_para_planilha(preco),
        "quantidade": estoque,
        "url_imagens": _normalizar_imagens("|".join(imagens[:8])),
        "fonte_extracao": "heuristica",
    }


def _get_openai_client_and_model():
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            openai_section = st.secrets.get("openai", {})
            if isinstance(openai_section, dict):
                api_key = api_key or openai_section.get("api_key", "")
                model = openai_section.get("model", model) or model
    except Exception:
        pass

    if not api_key or OpenAI is None:
        return None, model

    try:
        return OpenAI(api_key=api_key), model
    except Exception:
        return None, model


def _gpt_extrair_produto(url_produto: str, html: str, heuristica: dict) -> dict:
    client, model = _get_openai_client_and_model()
    if client is None:
        return heuristica

    soup = BeautifulSoup(html, "lxml")
    texto_limpo = soup.get_text(" ", strip=True)[:18000]

    prompt = f"""
Extraia dados de produto a partir da página de fornecedor.

URL: {url_produto}
Heurística inicial: {json.dumps(heuristica, ensure_ascii=False)}
Texto da página: {texto_limpo}

Responda SOMENTE em JSON válido:
{{
  "codigo": "",
  "descricao": "",
  "categoria": "",
  "gtin": "",
  "ncm": "",
  "preco": "",
  "quantidade": "",
  "url_imagens": "",
  "observacoes": ""
}}

Regras:
- não invente
- se encontrar sem estoque, quantidade = "0"
- url_imagens com separador |
- preco no formato 19,90
"""

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)

        return {
            "url_produto": url_produto,
            "codigo": _safe_str(data.get("codigo")) or heuristica.get("codigo", ""),
            "descricao": _safe_str(data.get("descricao")) or heuristica.get("descricao", ""),
            "categoria": _safe_str(data.get("categoria")) or heuristica.get("categoria", ""),
            "gtin": _safe_str(data.get("gtin")) or heuristica.get("gtin", ""),
            "ncm": _safe_str(data.get("ncm")) or heuristica.get("ncm", ""),
            "preco": _normalizar_preco_para_planilha(
                _safe_str(data.get("preco")) or heuristica.get("preco", "")
            ),
            "quantidade": _safe_str(data.get("quantidade")) or heuristica.get("quantidade", ""),
            "url_imagens": _normalizar_imagens(
                _safe_str(data.get("url_imagens")) or heuristica.get("url_imagens", "")
            ),
            "fonte_extracao": "gpt",
            "observacoes": _safe_str(data.get("observacoes")),
        }
    except Exception:
        return heuristica


def _descobrir_produtos_no_dominio(
    base_url: str,
    termo: str = "",
    max_paginas: int = 120,
    max_produtos: int = 1200,
    max_segundos: int = 180,
) -> list[str]:
    inicio = time.time()

    fila = deque(_rotas_iniciais(base_url, termo=termo))
    paginas_visitadas = set()
    produtos_encontrados = []
    produtos_vistos = set()

    while fila:
        if len(paginas_visitadas) >= max_paginas:
            break
        if len(produtos_encontrados) >= max_produtos:
            break
        if time.time() - inicio > max_segundos:
            break

        url_atual = fila.popleft()
        if url_atual in paginas_visitadas:
            continue

        paginas_visitadas.add(url_atual)

        try:
            html = _fetch_html_retry(url_atual, tentativas=2)
        except Exception:
            continue

        links_categoria, links_produto = _extrair_links_pagina(base_url, url_atual, html)

        for url_produto in links_produto:
            if url_produto not in produtos_vistos:
                produtos_vistos.add(url_produto)
                produtos_encontrados.append(url_produto)
                if len(produtos_encontrados) >= max_produtos:
                    break

        for url_categoria in links_categoria:
            if url_categoria not in paginas_visitadas and url_categoria not in fila:
                fila.append(url_categoria)

    return produtos_encontrados


def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
) -> pd.DataFrame:
    base_url = _normalizar_url(base_url)
    termo = _safe_str(termo)

    if not base_url:
        return pd.DataFrame()

    limite_tecnico = 1200
    if isinstance(limite_links, int) and limite_links > 0:
        limite_tecnico = min(max(limite_links, 1), 1200)

    produtos = _descobrir_produtos_no_dominio(
        base_url=base_url,
        termo=termo,
        max_paginas=120,
        max_produtos=limite_tecnico,
        max_segundos=180,
    )

    if not produtos:
        return pd.DataFrame()

    rows = []
    vistos = set()

    for url_produto in produtos:
        if url_produto in vistos:
            continue

        try:
            html_produto = _fetch_html_retry(url_produto, tentativas=2)
            heuristica = _extrair_detalhes_heuristicos(url_produto, html_produto)
            final = _gpt_extrair_produto(url_produto, html_produto, heuristica)

            if not _safe_str(final.get("descricao")):
                continue

            rows.append(final)
            vistos.add(url_produto)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")

    if "url_produto" in df.columns:
        df = df.drop_duplicates(subset=["url_produto"], keep="first")

    df = df.rename(
        columns={
            "codigo": "Código",
            "descricao": "Descrição",
            "categoria": "Categoria",
            "gtin": "GTIN",
            "ncm": "NCM",
            "preco": "Preço de custo",
            "quantidade": "Quantidade",
            "url_imagens": "URL Imagens",
            "url_produto": "URL Produto",
        }
    )

    colunas_ordenadas = [
        "Código",
        "Descrição",
        "Categoria",
        "GTIN",
        "NCM",
        "Preço de custo",
        "Quantidade",
        "URL Imagens",
        "URL Produto",
        "fonte_extracao",
        "observacoes",
    ]

    colunas_presentes = [c for c in colunas_ordenadas if c in df.columns]
    colunas_restantes = [c for c in df.columns if c not in colunas_presentes]

    return df[colunas_presentes + colunas_restantes].reset_index(drop=True)
