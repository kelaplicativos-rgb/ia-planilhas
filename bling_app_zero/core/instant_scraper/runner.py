# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

BLOCKED_LINK_PARTS = [
    "login",
    "conta",
    "account",
    "checkout",
    "carrinho",
    "cart",
    "wishlist",
    "favoritos",
    "politica",
    "privacidade",
    "termos",
    "whatsapp",
    "instagram",
    "facebook",
    "youtube",
    "mailto:",
    "tel:",
    "javascript:",
]

PRODUCT_WORDS = [
    "comprar",
    "produto",
    "preço",
    "preco",
    "price",
    "sku",
    "código",
    "codigo",
    "ref",
    "referência",
    "referencia",
]

OUTPUT_COLUMNS = [
    "url_produto",
    "nome",
    "sku",
    "marca",
    "categoria",
    "estoque",
    "preco",
    "gtin",
    "descricao",
    "imagens",
]


@dataclass
class CandidateBlock:
    selector: str
    score: int
    rows: List[Dict[str, Any]]


def _txt(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("\ufeff", "").replace("\x00", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _same_domain(url: str, base_url: str) -> bool:
    try:
        a = urlparse(url).netloc.lower().replace("www.", "")
        b = urlparse(base_url).netloc.lower().replace("www.", "")
        return a == b
    except Exception:
        return False


def _fetch(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=25,
            verify=False,
        )
        if resp.status_code >= 400:
            return ""
        return resp.text or ""
    except Exception:
        return ""


def _preco_para_float(value: Any) -> float:
    text = _txt(value)
    if not text:
        return 0.0

    match = re.search(r"(?:R\$)?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,.]\d{2})", text)
    if not match:
        return 0.0

    num = match.group(1)
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        num = num.replace(",", ".")

    try:
        return float(num)
    except Exception:
        return 0.0


def _extrair_preco_texto(text: str) -> str:
    text = _txt(text)
    match = re.search(r"(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+[,.]\d{2})", text)
    return _txt(match.group(1)) if match else ""


def _extrair_sku(text: str) -> str:
    text = _txt(text)
    patterns = [
        r"(?:SKU|CÓDIGO|CODIGO|CÓD|COD|REF|REFERÊNCIA|REFERENCIA)\s*[:\-]?\s*([A-Z0-9\-_./]{3,40})",
        r"\bSKU\s*([A-Z0-9\-_./]{3,40})",
    ]

    for pat in patterns:
        match = re.search(pat, text, flags=re.I)
        if match:
            return _txt(match.group(1))

    return ""


def _extrair_gtin(text: str) -> str:
    nums = re.findall(r"\b\d{8,14}\b", _txt(text))
    for n in nums:
        if len(n) in (8, 12, 13, 14):
            return n
    return ""


def _limpar_nome(nome: str) -> str:
    nome = _txt(nome)
    nome = re.sub(r"\s*[-|]\s*Mega Center.*$", "", nome, flags=re.I)
    nome = re.sub(r"\s*[-|]\s*Comprar.*$", "", nome, flags=re.I)
    nome = re.sub(r"\s*R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}.*$", "", nome, flags=re.I)
    return nome.strip(" -|")


def _estoque_por_texto(text: str) -> int:
    low = _txt(text).lower()

    if any(x in low for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "out of stock", "zerado"]):
        return 0

    match = re.search(r"(?:estoque|quantidade|qtd)\D{0,12}(\d+)", low)
    if match:
        try:
            return max(int(match.group(1)), 0)
        except Exception:
            return 0

    if any(x in low for x in ["em estoque", "disponível", "disponivel", "comprar", "adicionar ao carrinho"]):
        return 1

    return 0


def _imagem_valida(url: str) -> bool:
    low = url.lower()
    if not low.startswith(("http://", "https://")):
        return False
    if any(x in low for x in ["logo", "sprite", "placeholder", "banner", "icon", "facebook", "instagram"]):
        return False
    if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", low):
        return False
    return True


def _imagens_do_bloco(block, base_url: str) -> str:
    imgs: List[str] = []

    for img in block.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy")
        if not src:
            srcset = img.get("srcset") or ""
            if srcset:
                src = srcset.split(",")[0].strip().split(" ")[0].strip()

        if not src:
            continue

        abs_url = urljoin(base_url, src)
        if _imagem_valida(abs_url) and abs_url not in imgs:
            imgs.append(abs_url)

    return "|".join(imgs[:12])


def _link_do_bloco(block, base_url: str) -> str:
    links = []

    for a in block.select("a[href]"):
        href = _txt(a.get("href"))
        if not href:
            continue

        abs_url = urljoin(base_url, href)
        low = abs_url.lower()

        if not abs_url.startswith(("http://", "https://")):
            continue
        if not _same_domain(abs_url, base_url):
            continue
        if any(x in low for x in BLOCKED_LINK_PARTS):
            continue

        links.append(abs_url)

    if not links:
        return ""

    productish = [
        u for u in links
        if any(x in u.lower() for x in ["/produto", "/produtos", "/product", "/products", "/p/"])
    ]

    return productish[0] if productish else links[0]


def _nome_do_bloco(block) -> str:
    selectors = [
        "h1",
        "h2",
        "h3",
        ".product-name",
        ".product-title",
        ".nome-produto",
        ".titulo-produto",
        "[class*=product][class*=name]",
        "[class*=product][class*=title]",
        "[class*=nome]",
        "[class*=titulo]",
        "a[title]",
        "img[alt]",
    ]

    for sel in selectors:
        el = block.select_one(sel)
        if not el:
            continue

        if el.name == "a" and el.get("title"):
            nome = _txt(el.get("title"))
        elif el.name == "img" and el.get("alt"):
            nome = _txt(el.get("alt"))
        else:
            nome = _txt(el.get_text(" "))

        nome = _limpar_nome(nome)

        if len(nome) >= 4 and not nome.lower().startswith(("comprar", "ver mais", "adicionar")):
            return nome

    text = _txt(block.get_text(" "))
    text = re.sub(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}", "", text)

    partes = [p.strip() for p in re.split(r"\s{2,}| \| | - ", text) if len(p.strip()) >= 4]
    if partes:
        return _limpar_nome(partes[0][:180])

    return ""


def _row_from_block(block, base_url: str, categoria: str = "") -> Dict[str, Any]:
    text = _txt(block.get_text(" "))

    nome = _nome_do_bloco(block)
    preco = _extrair_preco_texto(text)
    sku = _extrair_sku(text)
    gtin = _extrair_gtin(text)
    imagens = _imagens_do_bloco(block, base_url)
    url_produto = _link_do_bloco(block, base_url)
    estoque = _estoque_por_texto(text)

    return {
        "url_produto": url_produto,
        "nome": nome,
        "sku": sku,
        "marca": "",
        "categoria": categoria,
        "estoque": estoque,
        "preco": _preco_para_float(preco),
        "gtin": gtin,
        "descricao": text[:1000],
        "imagens": imagens,
    }


def _score_row(row: Dict[str, Any]) -> int:
    score = 0

    if _txt(row.get("nome")):
        score += 3
    if _txt(row.get("url_produto")):
        score += 2
    if float(row.get("preco") or 0) > 0:
        score += 3
    if _txt(row.get("imagens")):
        score += 2
    if _txt(row.get("sku")):
        score += 1
    if _txt(row.get("gtin")):
        score += 1

    return score


def _selector_signature(el) -> str:
    classes = el.get("class") or []
    classes = [c for c in classes if c and len(c) <= 40]

    if classes:
        return f"{el.name}." + ".".join(classes[:3])

    return el.name


def _candidate_blocks(soup: BeautifulSoup, base_url: str) -> List[CandidateBlock]:
    groups: Dict[str, List[Any]] = {}

    for el in soup.find_all(["div", "li", "article", "section"]):
        text = _txt(el.get_text(" "))
        if len(text) < 20:
            continue

        low = text.lower()
        has_price = _preco_para_float(text) > 0
        has_product_word = any(w in low for w in PRODUCT_WORDS)
        has_img = bool(el.select_one("img"))
        has_link = bool(el.select_one("a[href]"))

        if not ((has_price or has_product_word) and (has_img or has_link)):
            continue

        sig = _selector_signature(el)
        groups.setdefault(sig, []).append(el)

    candidates: List[CandidateBlock] = []

    for sig, elements in groups.items():
        if len(elements) < 2:
            continue

        rows = [_row_from_block(el, base_url) for el in elements]
        rows = [r for r in rows if _score_row(r) >= 4]

        if len(rows) < 2:
            continue

        price_count = sum(1 for r in rows if float(r.get("preco") or 0) > 0)
        name_count = sum(1 for r in rows if _txt(r.get("nome")))
        img_count = sum(1 for r in rows if _txt(r.get("imagens")))
        url_count = sum(1 for r in rows if _txt(r.get("url_produto")))

        score = (len(rows) * 2) + (price_count * 3) + (name_count * 2) + img_count + url_count

        candidates.append(CandidateBlock(selector=sig, score=score, rows=rows))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _jsonld_products(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        items = []

        if isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items.extend(data["@graph"])
            else:
                items.append(data)
        elif isinstance(data, list):
            items.extend(data)

        for item in items:
            if not isinstance(item, dict):
                continue

            tipo = item.get("@type")
            if isinstance(tipo, list):
                is_product = any(str(t).lower() == "product" for t in tipo)
            else:
                is_product = str(tipo or "").lower() == "product"

            if not is_product:
                continue

            offers = item.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            images = item.get("image") or []
            if isinstance(images, str):
                images = [images]

            rows.append(
                {
                    "url_produto": _txt(item.get("url") or offers.get("url") or base_url),
                    "nome": _limpar_nome(item.get("name") or ""),
                    "sku": _txt(item.get("sku") or item.get("mpn") or ""),
                    "marca": _txt((item.get("brand") or {}).get("name") if isinstance(item.get("brand"), dict) else item.get("brand")),
                    "categoria": _txt(item.get("category") or ""),
                    "estoque": _estoque_por_texto(str(offers.get("availability") or "")),
                    "preco": _preco_para_float(offers.get("price") or ""),
                    "gtin": _extrair_gtin(" ".join([_txt(item.get(k)) for k in ["gtin8", "gtin12", "gtin13", "gtin14"] if item.get(k)])),
                    "descricao": _txt(item.get("description") or ""),
                    "imagens": "|".join([urljoin(base_url, img) for img in images if _imagem_valida(urljoin(base_url, img))][:12]),
                }
            )

    return [r for r in rows if _score_row(r) >= 4]


def _categoria_da_pagina(soup: BeautifulSoup) -> str:
    crumbs = []

    for sel in [
        ".breadcrumb a",
        ".breadcrumbs a",
        "[class*=breadcrumb] a",
        "[class*=breadcrumbs] a",
    ]:
        for a in soup.select(sel):
            t = _txt(a.get_text(" "))
            if t and t.lower() not in {"home", "início", "inicio"}:
                crumbs.append(t)

    seen = []
    for c in crumbs:
        if c not in seen:
            seen.append(c)

    return " > ".join(seen[:6])


def _next_page_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    out: List[str] = []

    for a in soup.select("a[href]"):
        href = _txt(a.get("href"))
        text = _txt(a.get_text(" ")).lower()
        abs_url = urljoin(base_url, href)
        low = abs_url.lower()

        if not abs_url.startswith(("http://", "https://")):
            continue
        if not _same_domain(abs_url, base_url):
            continue
        if any(x in low for x in BLOCKED_LINK_PARTS):
            continue

        is_page = (
            re.search(r"[?&](page|p|pagina)=\d+", low)
            or re.search(r"/(page|pagina)/\d+", low)
            or text in {"próximo", "proximo", "next", ">", "»"}
        )

        if is_page and abs_url not in out:
            out.append(abs_url)

    return out[:3]


def _normalizar_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = pd.DataFrame(rows).fillna("")

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["nome"] = df["nome"].apply(_limpar_nome)
    df["url_produto"] = df["url_produto"].apply(_txt)
    df["sku"] = df["sku"].apply(_txt)
    df["marca"] = df["marca"].apply(_txt)
    df["categoria"] = df["categoria"].apply(_txt)
    df["descricao"] = df["descricao"].apply(_txt)
    df["gtin"] = df["gtin"].apply(lambda x: re.sub(r"\D", "", _txt(x)) if len(re.sub(r"\D", "", _txt(x))) in (8, 12, 13, 14) else "")
    df["imagens"] = df["imagens"].apply(_txt)
    df["preco"] = df["preco"].apply(_preco_para_float)
    df["estoque"] = df["estoque"].apply(lambda x: max(int(float(x or 0)), 0) if str(x or "").replace(".", "", 1).isdigit() else _estoque_por_texto(x))

    df = df[
        (df["nome"].astype(str).str.strip() != "")
        | (df["url_produto"].astype(str).str.strip() != "")
    ]

    keys = []
    for _, row in df.iterrows():
        key = (
            _txt(row.get("url_produto"))
            or _txt(row.get("sku"))
            or _txt(row.get("gtin"))
            or _txt(row.get("nome"))
        ).lower()
        keys.append(key)

    df["_key"] = keys
    df = df[df["_key"] != ""]
    df = df.drop_duplicates(subset=["_key"], keep="first")
    df = df.drop(columns=["_key"], errors="ignore")

    return df[OUTPUT_COLUMNS].reset_index(drop=True)


def _extract_from_page(url: str, html: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    soup = BeautifulSoup(html or "", "lxml")
    categoria = _categoria_da_pagina(soup)

    jsonld_rows = _jsonld_products(soup, url)
    for row in jsonld_rows:
        if not row.get("categoria"):
            row["categoria"] = categoria

    candidates = _candidate_blocks(soup, url)

    dom_rows: List[Dict[str, Any]] = []
    if candidates:
        dom_rows = candidates[0].rows
        for row in dom_rows:
            if not row.get("categoria"):
                row["categoria"] = categoria

    rows = jsonld_rows if len(jsonld_rows) >= len(dom_rows) else dom_rows
    next_links = _next_page_links(soup, url)

    return rows, next_links


def run_scraper(url: str, max_pages: int = 5, **kwargs) -> pd.DataFrame:
    """
    Instant Data Scraper REAL:
    - Lê a página atual.
    - Detecta automaticamente blocos repetidos de produto.
    - Prioriza JSON-LD quando existir.
    - Segue poucas paginações com limite rígido.
    - Não faz crawl profundo.
    - Não entra em loop infinito.
    """

    start_url = _normalizar_url(url)
    if not start_url:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    max_pages = max(1, min(int(max_pages or 5), 10))

    visited = set()
    queue = [start_url]
    all_rows: List[Dict[str, Any]] = []

    while queue and len(visited) < max_pages:
        current = queue.pop(0)

        if current in visited:
            continue

        visited.add(current)

        html = _fetch(current)
        if not html:
            continue

        rows, next_links = _extract_from_page(current, html)
        all_rows.extend(rows)

        for link in next_links:
            if link not in visited and link not in queue and len(queue) < max_pages:
                queue.append(link)

    return _normalizar_df(all_rows)


def buscar_dataframe(url: str, max_pages: int = 5, **kwargs) -> pd.DataFrame:
    return run_scraper(url, max_pages=max_pages, **kwargs)


def buscar_produtos(url: str, max_pages: int = 5, **kwargs) -> List[Dict[str, Any]]:
    df = run_scraper(url, max_pages=max_pages, **kwargs)
    return df.fillna("").to_dict(orient="records")
