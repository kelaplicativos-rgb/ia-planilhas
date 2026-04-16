
from __future__ import annotations

import json
import os
import re
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
    )
}


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


def _extrair_preco(texto: str) -> str:
    texto = _safe_str(texto)
    if not texto:
        return ""
    match = re.search(r"R\$\s*\d[\d\.\,]*", texto, flags=re.I)
    return match.group(0).strip() if match else ""


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
    texto = texto.replace("\n", "|").replace("\r", "|").replace(";", "|").replace(",", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]
    vistos = set()
    urls = []
    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)
    return "|".join(urls)


def _montar_urls_busca(base_url: str, termo: str) -> list[str]:
    base = _normalizar_url(base_url)
    q = quote_plus(_safe_str(termo))

    urls = [
        f"{base}/search?q={q}",
        f"{base}/busca?q={q}",
        f"{base}/busca?search={q}",
        f"{base}/busca?descricao={q}",
        f"{base}/catalogsearch/result/?q={q}",
        f"{base}/?s={q}",
        f"{base}/?q={q}",
    ]

    saida = []
    vistos = set()
    for url in urls:
        if url not in vistos:
            vistos.add(url)
            saida.append(url)
    return saida


def _fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _extrair_links_produto(base_url: str, html: str, termo: str, limite: int = 40) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    resultados = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = _safe_str(a.get("href"))
        if not href:
            continue

        url = urljoin(base_url, href)
        if not _mesmo_dominio(base_url, url):
            continue
        if url in vistos:
            continue

        texto = " ".join(a.stripped_strings).strip()
        bloco_texto = ""
        try:
            bloco_texto = a.parent.get_text(" ", strip=True)[:600]
        except Exception:
            bloco_texto = texto

        url_n = _normalizar_texto(url)
        texto_n = _normalizar_texto(texto)
        termo_n = _normalizar_texto(termo)

        parece_produto = (
            "/produto" in url_n
            or "/product" in url_n
            or "/p/" in url_n
            or "sku" in url_n
            or (termo_n and termo_n in texto_n)
        )

        if not parece_produto:
            continue

        resultados.append(
            {
                "url_produto": url,
                "titulo_bloco": texto,
                "preco_bloco": _extrair_preco(bloco_texto),
                "texto_bloco": bloco_texto,
            }
        )
        vistos.add(url)

        if len(resultados) >= limite:
            break

    return resultados


def _extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    titulo = ""
    for sel in ["h1", '[class*="product"] h1', '[class*="title"]']:
        el = soup.select_one(sel)
        if el:
            titulo = _safe_str(el.get_text(" ", strip=True))
            if titulo:
                break

    texto_total = soup.get_text(" ", strip=True)
    preco = _extrair_preco(texto_total)

    imagens = []
    for img in soup.find_all("img", src=True):
        src = _safe_str(img.get("src"))
        if not src:
            continue
        url_img = urljoin(url_produto, src)
        if _mesmo_dominio(url_produto, url_img):
            imagens.append(url_img)

    codigo = ""
    gtin = ""
    ncm = ""

    padroes_codigo = [
        r"(?:sku|c[oó]d(?:igo)?)[\s:\-#]*([A-Za-z0-9\-_\.\/]+)",
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
    texto_limpo = soup.get_text(" ", strip=True)
    texto_limpo = texto_limpo[:18000]

    prompt = f"""
Extraia dados de produto a partir do HTML/texto de uma página de fornecedor.

URL:
{url_produto}

Heurística inicial:
{json.dumps(heuristica, ensure_ascii=False)}

Texto da página:
{texto_limpo}

Responda SOMENTE em JSON válido neste formato:
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
- não invente valores
- se encontrar indicação clara de sem estoque, quantidade = "0"
- url_imagens deve usar separador |
- preco deve vir em formato brasileiro com vírgula, ex: 19,90
- priorize descrição comercial do produto
- código pode ser SKU, código, referência ou similar
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

        saida = {
            "url_produto": url_produto,
            "codigo": _safe_str(data.get("codigo")) or heuristica.get("codigo", ""),
            "descricao": _safe_str(data.get("descricao")) or heuristica.get("descricao", ""),
            "categoria": _safe_str(data.get("categoria")) or heuristica.get("categoria", ""),
            "gtin": _safe_str(data.get("gtin")) or heuristica.get("gtin", ""),
            "ncm": _safe_str(data.get("ncm")) or heuristica.get("ncm", ""),
            "preco": _normalizar_preco_para_planilha(_safe_str(data.get("preco")) or heuristica.get("preco", "")),
            "quantidade": _safe_str(data.get("quantidade")) or heuristica.get("quantidade", ""),
            "url_imagens": _normalizar_imagens(_safe_str(data.get("url_imagens")) or heuristica.get("url_imagens", "")),
            "fonte_extracao": "gpt",
            "observacoes": _safe_str(data.get("observacoes")),
        }
        return saida

    except Exception:
        return heuristica


def buscar_produtos_site_com_gpt(base_url: str, termo: str, limite_links: int = 20) -> pd.DataFrame:
    base_url = _normalizar_url(base_url)
    termo = _safe_str(termo)

    if not base_url or not termo:
        return pd.DataFrame()

    links = []
    for url_busca in _montar_urls_busca(base_url, termo):
        try:
            html_busca = _fetch_html(url_busca)
            links = _extrair_links_produto(base_url, html_busca, termo, limite=limite_links)
            if links:
                break
        except Exception:
            continue

    if not links:
        return pd.DataFrame()

    rows = []
    vistos = set()

    for item in links:
        url_produto = item["url_produto"]
        if url_produto in vistos:
            continue

        try:
            html_produto = _fetch_html(url_produto)
            heuristica = _extrair_detalhes_heuristicos(url_produto, html_produto)

            if not heuristica.get("descricao"):
                heuristica["descricao"] = item.get("titulo_bloco", "")
            if not heuristica.get("preco"):
                heuristica["preco"] = _normalizar_preco_para_planilha(item.get("preco_bloco", ""))

            final = _gpt_extrair_produto(url_produto, html_produto, heuristica)
            rows.append(final)
            vistos.add(url_produto)

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")
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

    return df
