
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

TIMEOUT = 20
MAX_PAGINAS_PADRAO = 12
MAX_THREADS_PADRAO = 5


# ============================================================
# LOG
# ============================================================

def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.utils.excel_logs import log_debug as _log_excel

        _log_excel(msg, nivel)
        return
    except Exception:
        pass

    try:
        from bling_app_zero.ui.app_helpers import log_debug as _log_ui

        _log_ui(msg, nivel)
        return
    except Exception:
        pass


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _safe_int(valor: Any, default: int = 0) -> int:
    try:
        return int(float(str(valor).replace(",", ".")))
    except Exception:
        return default


def _normalizar_texto(valor: Any) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "\xa0": " ",
        "_": " ",
        "-": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _baixar_html(url: str) -> str:
    resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def _soup(url: str) -> BeautifulSoup:
    html = _baixar_html(url)
    return BeautifulSoup(html, "html.parser")


def _deduplicar_ordem(valores: Iterable[str]) -> list[str]:
    vistos = set()
    saida: list[str] = []
    for valor in valores:
        texto = _safe_str(valor)
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        saida.append(texto)
    return saida


def _url_mesmo_dominio(url_a: str, url_b: str) -> bool:
    try:
        dom_a = urlparse(url_a).netloc.replace("www.", "")
        dom_b = urlparse(url_b).netloc.replace("www.", "")
        return dom_a == dom_b
    except Exception:
        return False


def _normalizar_url_base(url: str) -> str:
    texto = _safe_str(url)
    if not texto:
        return ""
    if not texto.startswith(("http://", "https://")):
        texto = "https://" + texto
    return texto


def _to_float_brasil(valor: Any) -> float:
    texto = _safe_str(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _formatar_numero_bling(valor: Any) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


# ============================================================
# JSON-LD
# ============================================================

def _extrair_jsonld(soup: BeautifulSoup) -> list[dict]:
    itens: list[dict] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = _safe_str(tag.string or tag.get_text(" ", strip=True))
        if not bruto:
            continue

        try:
            dado = json.loads(bruto)
            if isinstance(dado, list):
                itens.extend([x for x in dado if isinstance(x, dict)])
            elif isinstance(dado, dict):
                itens.append(dado)
        except Exception:
            continue

    return itens


# ============================================================
# DETECÇÃO DE LINKS DE PRODUTO
# ============================================================

def _pontuar_link_produto(url: str, texto_link: str) -> int:
    url_n = _normalizar_texto(url)
    txt_n = _normalizar_texto(texto_link)
    score = 0

    # padrões clássicos
    if "/produto/" in url_n or "/product/" in url_n:
        score += 10
    if "/p/" in url_n:
        score += 6
    if any(x in url_n for x in ["sku", "item", "prod-"]):
        score += 4

    # urls com ids grandes
    if re.search(r"/\d{5,}", url_n):
        score += 4

    # texto de link com cara de produto
    if len(txt_n.split()) >= 3:
        score += 2
    if any(x in txt_n for x in ["ver detalhes", "comprar", "produto"]):
        score += 1

    # evitar links ruins
    if any(
        x in url_n
        for x in [
            "whatsapp",
            "instagram",
            "facebook",
            "login",
            "conta",
            "carrinho",
            "checkout",
            "ajuda",
            "politica",
            "privacidade",
            "termos",
        ]
    ):
        score -= 20

    return score


def _coletar_links_produto(url_lista: str, max_paginas: int = 12) -> list[str]:
    url_lista = _normalizar_url_base(url_lista)
    paginas = [url_lista]
    links_encontrados: list[str] = []

    for pagina_url in paginas[: max(1, max_paginas)]:
        try:
            soup = _soup(pagina_url)
        except Exception as e:
            _log_debug(f"[CRAWLER] erro lendo página de lista {pagina_url} | {e}", "WARNING")
            continue

        pagina_links: list[str] = []

        for a in soup.find_all("a", href=True):
            href = urljoin(pagina_url, a.get("href"))
            texto = _safe_str(a.get_text(" ", strip=True))

            if not _url_mesmo_dominio(url_lista, href):
                continue

            if _pontuar_link_produto(href, texto) >= 5:
                pagina_links.append(href)

        links_encontrados.extend(pagina_links)
        _log_debug(f"[CRAWLER] links detectados na página {pagina_url}: {len(pagina_links)}", "INFO")

        # paginação
        for a in soup.find_all("a", href=True):
            href = urljoin(pagina_url, a.get("href"))
            texto = _normalizar_texto(a.get_text(" ", strip=True))

            if not _url_mesmo_dominio(url_lista, href):
                continue

            if (
                any(x in texto for x in ["proxima", "próxima", "next"])
                or "page=" in href.lower()
                or re.search(r"/pagina/\d+", href.lower())
            ):
                if href not in paginas and len(paginas) < max_paginas:
                    paginas.append(href)

    links_encontrados = _deduplicar_ordem(links_encontrados)
    _log_debug(f"[CRAWLER] total de links de produto detectados: {len(links_encontrados)}", "INFO")
    return links_encontrados


# ============================================================
# EXTRAÇÃO DE CAMPOS
# ============================================================

def _buscar_primeiro_texto(soup: BeautifulSoup, seletores: list[str]) -> str:
    for seletor in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = _safe_str(el.get_text(" ", strip=True))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def _buscar_primeiro_atributo(soup: BeautifulSoup, seletores: list[tuple[str, str]]) -> str:
    for seletor, atributo in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                valor = _safe_str(el.get(atributo))
                if valor:
                    return valor
        except Exception:
            continue
    return ""


def _extrair_nome(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        nome = _safe_str(item.get("name"))
        if nome:
            return nome

    return _buscar_primeiro_texto(
        soup,
        [
            "h1",
            ".product-title",
            ".product-name",
            ".nome-produto",
            '[itemprop="name"]',
            "title",
        ],
    )


def _extrair_descricao_longa(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        descricao = _safe_str(item.get("description"))
        if descricao:
            return descricao

    return _buscar_primeiro_texto(
        soup,
        [
            ".product-description",
            ".descricao",
            ".description",
            ".tabs-description",
            '[itemprop="description"]',
        ],
    )


def _extrair_preco(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        offers = item.get("offers")
        if isinstance(offers, dict):
            preco = offers.get("price") or offers.get("lowPrice")
            if _to_float_brasil(preco) > 0:
                return _formatar_numero_bling(preco)

    meta_preco = _buscar_primeiro_atributo(
        soup,
        [
            ('meta[itemprop="price"]', "content"),
            ('meta[property="product:price:amount"]', "content"),
            ('meta[name="twitter:data1"]', "content"),
        ],
    )
    if _to_float_brasil(meta_preco) > 0:
        return _formatar_numero_bling(meta_preco)

    texto_preco = _buscar_primeiro_texto(
        soup,
        [
            '[itemprop="price"]',
            ".price",
            ".preco",
            ".product-price",
            ".preco-por",
            ".price-current",
            ".valor",
        ],
    )
    if texto_preco:
        encontrado = re.search(r"R\$\s*([\d\.\,]+)", texto_preco)
        if encontrado:
            return _formatar_numero_bling(encontrado.group(1))
        if _to_float_brasil(texto_preco) > 0:
            return _formatar_numero_bling(texto_preco)

    html_texto = soup.get_text(" ", strip=True)
    encontrado = re.search(r"R\$\s*([\d\.\,]+)", html_texto)
    if encontrado:
        return _formatar_numero_bling(encontrado.group(1))

    return ""


def _extrair_codigo(soup: BeautifulSoup, jsonlds: list[dict], url_produto: str) -> str:
    for item in jsonlds:
        for chave in ["sku", "productID", "mpn", "gtin13", "gtin", "gtin12", "gtin14", "gtin8"]:
            valor = _safe_str(item.get(chave))
            if valor:
                return re.sub(r"\s+", "", valor)

    html_texto = soup.get_text(" ", strip=True)
    padroes = [
        r"(?:codigo|c[oó]digo|sku|ref)\s*[:#]?\s*([A-Za-z0-9\-_\.]{4,})",
        r"\b([0-9]{8,14})\b",
    ]
    for padrao in padroes:
        encontrado = re.search(padrao, html_texto, re.IGNORECASE)
        if encontrado:
            return _safe_str(encontrado.group(1))

    slug = urlparse(url_produto).path.strip("/").split("/")[-1]
    return _safe_str(slug)[:60]


def _extrair_gtin(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin"]:
            valor = _safe_str(item.get(chave))
            numeros = re.sub(r"\D", "", valor)
            if len(numeros) in {8, 12, 13, 14}:
                return numeros

    html_texto = soup.get_text(" ", strip=True)
    encontrado = re.search(
        r"(?:gtin|ean|codigo de barras)\s*[:#]?\s*([0-9]{8,14})",
        html_texto,
        re.IGNORECASE,
    )
    if encontrado:
        return encontrado.group(1)

    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    for seletor in [
        ".breadcrumb a",
        ".breadcrumbs a",
        '[aria-label="breadcrumb"] a',
    ]:
        els = soup.select(seletor)
        if els:
            partes = [_safe_str(x.get_text(" ", strip=True)) for x in els]
            partes = [x for x in partes if x]
            if partes:
                return " > ".join(partes)
    return ""


def _extrair_imagens(soup: BeautifulSoup, url_produto: str, jsonlds: list[dict]) -> str:
    imagens: list[str] = []

    for item in jsonlds:
        valor = item.get("image")
        if isinstance(valor, list):
            imagens.extend([_safe_str(x) for x in valor if _safe_str(x)])
        elif isinstance(valor, str):
            imagens.append(valor)

    og_image = _buscar_primeiro_atributo(
        soup,
        [
            ('meta[property="og:image"]', "content"),
            ('meta[name="twitter:image"]', "content"),
        ],
    )
    if og_image:
        imagens.append(og_image)

    for img in soup.select("img"):
        src = _safe_str(img.get("src") or img.get("data-src") or img.get("data-lazy"))
        if not src:
            continue
        src = urljoin(url_produto, src)
        if _url_mesmo_dominio(url_produto, src):
            imagens.append(src)

    imagens = [
        urljoin(url_produto, i)
        for i in imagens
        if i and not any(bad in i.lower() for bad in ["icon", "logo", "sprite", "base64"])
    ]
    imagens = _deduplicar_ordem(imagens[:10])
    return "|".join(imagens)


def _extrair_quantidade_real(soup: BeautifulSoup, jsonlds: list[dict], padrao_disponivel: int) -> int:
    for item in jsonlds:
        offers = item.get("offers")
        if isinstance(offers, dict):
            quantidade = offers.get("inventoryLevel")
            if isinstance(quantidade, dict):
                valor = quantidade.get("value")
                if str(valor).isdigit():
                    return int(valor)
            if isinstance(quantidade, (int, float, str)) and str(quantidade).isdigit():
                return int(quantidade)

            disponibilidade = _safe_str(offers.get("availability")).lower()
            if "outofstock" in disponibilidade:
                return 0
            if "instock" in disponibilidade:
                return max(1, int(padrao_disponivel))

    html_texto = _normalizar_texto(soup.get_text(" ", strip=True))

    padroes_num = [
        r"estoque\s*[:\-]?\s*(\d+)",
        r"quantidade\s*disponivel\s*[:\-]?\s*(\d+)",
        r"restam\s*(\d+)",
        r"apenas\s*(\d+)\s*(?:unidades|itens|pecas|peças)",
    ]
    for padrao in padroes_num:
        achado = re.search(padrao, html_texto, re.IGNORECASE)
        if achado:
            try:
                return int(achado.group(1))
            except Exception:
                pass

    if any(x in html_texto for x in ["sem estoque", "esgotado", "indisponivel", "indisponível", "zerado"]):
        return 0
    if any(x in html_texto for x in ["ultimas unidades", "últimas unidades", "ultimas pecas", "últimas peças"]):
        return 3
    if any(x in html_texto for x in ["em estoque", "disponivel", "disponível", "a pronta entrega"]):
        return max(1, int(padrao_disponivel))

    return max(1, int(padrao_disponivel))


# ============================================================
# EXTRAÇÃO DE PRODUTO
# ============================================================

def _extrair_produto(url_produto: str, padrao_disponivel: int) -> dict:
    try:
        soup = _soup(url_produto)
        jsonlds = _extrair_jsonld(soup)

        nome = _extrair_nome(soup, jsonlds)
        if not nome:
            return {}

        return {
            "codigo_fornecedor": _extrair_codigo(soup, jsonlds, url_produto),
            "descricao_fornecedor": nome,
            "descricao_longa": _extrair_descricao_longa(soup, jsonlds),
            "preco_base": _extrair_preco(soup, jsonlds),
            "quantidade_real": _extrair_quantidade_real(soup, jsonlds, padrao_disponivel),
            "gtin": _extrair_gtin(soup, jsonlds),
            "categoria": _extrair_categoria(soup),
            "url_imagens": _extrair_imagens(soup, url_produto, jsonlds),
            "link_produto": url_produto,
        }
    except Exception as e:
        _log_debug(f"[CRAWLER] erro extraindo produto {url_produto} | {e}", "WARNING")
        return {}


# ============================================================
# FALLBACK DE PÁGINA ÚNICA
# ============================================================

def _tentar_produto_unico(url: str, padrao_disponivel: int) -> pd.DataFrame:
    try:
        produto = _extrair_produto(url, padrao_disponivel)
        if produto and _safe_str(produto.get("descricao_fornecedor")):
            _log_debug("[CRAWLER] página interpretada como produto único", "INFO")
            return pd.DataFrame([produto]).fillna("")
    except Exception as e:
        _log_debug(f"[CRAWLER] fallback produto único falhou | {e}", "WARNING")
    return pd.DataFrame()


# ============================================================
# EXECUTOR PRINCIPAL
# ============================================================

def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS_PADRAO,
    max_threads: int = MAX_THREADS_PADRAO,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:
    url = _normalizar_url_base(url)
    if not url:
        return pd.DataFrame()

    max_paginas = max(1, _safe_int(max_paginas, MAX_PAGINAS_PADRAO))
    max_threads = max(1, min(_safe_int(max_threads, MAX_THREADS_PADRAO), 8))
    padrao_disponivel = max(0, _safe_int(padrao_disponivel, 10))

    _log_debug(
        f"[CRAWLER] iniciar | url={url} | max_paginas={max_paginas} | max_threads={max_threads}",
        "INFO",
    )

    links = _coletar_links_produto(url, max_paginas=max_paginas)

    if not links:
        _log_debug("[CRAWLER] nenhum link detectado; tentando fallback de produto único", "WARNING")
        return _tentar_produto_unico(url, padrao_disponivel)

    resultados: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futuros = {
            executor.submit(_extrair_produto, link, padrao_disponivel): link
            for link in links
        }

        for i, futuro in enumerate(as_completed(futuros), start=1):
            link = futuros[futuro]
            try:
                produto = futuro.result()
                if produto:
                    resultados.append(produto)

                if i % 10 == 0:
                    _log_debug(f"[CRAWLER] progresso: {i}/{len(links)}", "INFO")
            except Exception as e:
                _log_debug(f"[CRAWLER] erro thread {link} | {e}", "WARNING")

    if not resultados:
        _log_debug("[CRAWLER] nenhum produto válido extraído", "ERROR")
        return pd.DataFrame()

    df = pd.DataFrame(resultados).fillna("")

    if "link_produto" in df.columns:
        df = df.drop_duplicates(subset=["link_produto"], keep="first")
    elif "descricao_fornecedor" in df.columns:
        df = df.drop_duplicates(subset=["descricao_fornecedor"], keep="first")

    if "preco_base" in df.columns:
        df["preco_base"] = df["preco_base"].apply(_formatar_numero_bling)

    if "quantidade_real" in df.columns:
        df["quantidade_real"] = pd.to_numeric(
            df["quantidade_real"], errors="coerce"
        ).fillna(0).astype(int)

    colunas_finais = [
        "codigo_fornecedor",
        "descricao_fornecedor",
        "descricao_longa",
        "preco_base",
        "quantidade_real",
        "gtin",
        "categoria",
        "url_imagens",
        "link_produto",
    ]

    for coluna in colunas_finais:
        if coluna not in df.columns:
            df[coluna] = ""

    _log_debug(f"[CRAWLER] finalizado com {len(df)} produto(s)", "SUCCESS")
    return df[
