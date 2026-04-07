from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "output"))
FORNECEDORES_DB_PATH = os.path.join(OUTPUT_DIR, "fornecedores_adaptativos.json")


# ==========================================================
# BASE / ARQUIVO
# ==========================================================
def _garantir_pasta() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _texto_limpo(valor: Any) -> str:
    texto = unescape(str(valor or ""))
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _slug(texto: str) -> str:
    texto = _texto_limpo(texto).lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _load_db() -> dict[str, Any]:
    _garantir_pasta()

    if not os.path.exists(FORNECEDORES_DB_PATH):
        return {}

    try:
        with open(FORNECEDORES_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_db(data: dict[str, Any]) -> None:
    _garantir_pasta()
    with open(FORNECEDORES_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==========================================================
# DOMÍNIO
# ==========================================================
def extrair_dominio(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
        host = host.replace("www.", "").strip()
        return host
    except Exception:
        return ""


# ==========================================================
# BANCO DE FORNECEDORES
# ==========================================================
def carregar_fornecedor(dominio: str) -> dict[str, Any]:
    dominio = extrair_dominio(dominio)
    if not dominio:
        return {}

    db = _load_db()
    item = db.get(dominio, {})
    return item if isinstance(item, dict) else {}


def listar_fornecedores() -> dict[str, Any]:
    return _load_db()


def salvar_fornecedor(
    dominio: str,
    config: dict[str, Any],
    sobrescrever: bool = False,
) -> bool:
    dominio = extrair_dominio(dominio)
    if not dominio or not isinstance(config, dict) or not config:
        return False

    db = _load_db()

    if dominio in db and not sobrescrever:
        return False

    atual = db.get(dominio, {}) if isinstance(db.get(dominio, {}), dict) else {}

    novo_item = {
        "dominio": dominio,
        "tipo": str(config.get("tipo", atual.get("tipo", "generico")) or "generico").strip(),
        "confianca": float(config.get("confianca", atual.get("confianca", 0.0)) or 0.0),
        "seletores": config.get("seletores", atual.get("seletores", {})) or {},
        "links": config.get("links", atual.get("links", {})) or {},
        "imagens_multiplas": bool(config.get("imagens_multiplas", atual.get("imagens_multiplas", True))),
        "origem": str(config.get("origem", atual.get("origem", "ia_adaptativa")) or "ia_adaptativa").strip(),
    }

    db[dominio] = novo_item
    _save_db(db)
    return True


def atualizar_fornecedor(
    dominio: str,
    patch: dict[str, Any],
) -> bool:
    dominio = extrair_dominio(dominio)
    if not dominio or not isinstance(patch, dict):
        return False

    db = _load_db()
    atual = db.get(dominio, {})
    if not isinstance(atual, dict):
        atual = {}

    if "seletores" in patch and isinstance(patch["seletores"], dict):
        seletores = atual.get("seletores", {})
        if not isinstance(seletores, dict):
            seletores = {}
        for chave, valor in patch["seletores"].items():
            if valor:
                seletores[chave] = valor
        atual["seletores"] = seletores

    if "links" in patch and isinstance(patch["links"], dict):
        links = atual.get("links", {})
        if not isinstance(links, dict):
            links = {}
        for chave, valor in patch["links"].items():
            if valor:
                links[chave] = valor
        atual["links"] = links

    for chave in ["tipo", "origem"]:
        if chave in patch and patch.get(chave) is not None:
            atual[chave] = patch.get(chave)

    if "confianca" in patch and patch.get("confianca") is not None:
        try:
            atual["confianca"] = float(patch.get("confianca"))
        except Exception:
            pass

    if "imagens_multiplas" in patch:
        atual["imagens_multiplas"] = bool(patch.get("imagens_multiplas"))

    db[dominio] = atual
    _save_db(db)
    return True


# ==========================================================
# IA ADAPTATIVA (HEURÍSTICA)
# ==========================================================
def _coletar_classes(el) -> str:
    try:
        classes = el.get("class", []) or []
        if isinstance(classes, str):
            return classes.strip()
        return " ".join(str(c).strip() for c in classes if str(c).strip())
    except Exception:
        return ""


def _css_path_simples(el) -> str:
    try:
        nome = (el.name or "").strip()
        if not nome:
            return ""

        el_id = _texto_limpo(el.get("id"))
        if el_id:
            return f"{nome}#{el_id}"

        classes = _coletar_classes(el)
        if classes:
            primeira = classes.split()[0].strip()
            if primeira:
                return f"{nome}.{primeira}"

        return nome
    except Exception:
        return ""


def _escolher_primeiro_valido(candidatos: list[str]) -> list[str]:
    vistos = set()
    saida = []

    for item in candidatos:
        item = _texto_limpo(item)
        if not item:
            continue
        if item in vistos:
            continue
        vistos.add(item)
        saida.append(item)

    return saida[:8]


def _detectar_tipo_loja(html: str, soup: BeautifulSoup) -> str:
    texto = (html or "").lower()

    if "woocommerce" in texto or soup.select_one(".woocommerce") or soup.select_one(".product_title"):
        return "woocommerce"

    if "shopify" in texto or "cdn.shopify.com" in texto or soup.select_one("[class*='shopify']"):
        return "shopify"

    if "vtex" in texto or "__vtex" in texto or soup.select_one("[class*='vtex']"):
        return "vtex"

    return "generico"


def _detectar_selectores_nome(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        "h1",
        "h1.product_title",
        ".product-title",
        ".product-name",
        ".produto_nome",
        ".product_title",
        "[itemprop='name']",
    ]

    encontrados = []

    for sel in candidatos:
        try:
            el = soup.select_one(sel)
            if el and _texto_limpo(el.get_text(" ", strip=True)):
                encontrados.append(sel)
        except Exception:
            continue

    for el in soup.find_all(["h1", "h2"]):
        texto = _texto_limpo(el.get_text(" ", strip=True))
        if len(texto) >= 4:
            path = _css_path_simples(el)
            if path:
                encontrados.append(path)

    return _escolher_primeiro_valido(encontrados)


def _detectar_selectores_preco(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        ".price",
        ".valor",
        ".product-price",
        ".price-current",
        ".special-price",
        ".final-price",
        ".woocommerce-Price-amount",
        "[itemprop='price']",
        "meta[property='product:price:amount']",
        "meta[property='og:price:amount']",
    ]

    encontrados = []

    for sel in candidatos:
        try:
            el = soup.select_one(sel)
            if not el:
                continue

            if el.name == "meta":
                val = _texto_limpo(el.get("content"))
            else:
                val = _texto_limpo(el.get_text(" ", strip=True))

            if val:
                encontrados.append(sel)
        except Exception:
            continue

    for el in soup.find_all(True):
        classes = _coletar_classes(el).lower()
        if "price" in classes or "preco" in classes or "valor" in classes:
            texto = _texto_limpo(el.get_text(" ", strip=True))
            if texto:
                path = _css_path_simples(el)
                if path:
                    encontrados.append(path)

    return _escolher_primeiro_valido(encontrados)


def _detectar_selectores_descricao(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        ".description",
        ".product-description",
        ".woocommerce-product-details__short-description",
        "[itemprop='description']",
        "[class*='description']",
        "[class*='descricao']",
        ".tab-description",
        "#description",
        "meta[property='og:description']",
        "meta[name='description']",
    ]

    encontrados = []

    for sel in candidatos:
        try:
            el = soup.select_one(sel)
            if not el:
                continue

            if el.name == "meta":
                val = _texto_limpo(el.get("content"))
            else:
                val = _texto_limpo(el.get_text(" ", strip=True))

            if val:
                encontrados.append(sel)
        except Exception:
            continue

    return _escolher_primeiro_valido(encontrados)


def _detectar_selectores_imagem(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        ".product-gallery img",
        ".woocommerce-product-gallery img",
        "[class*='gallery'] img",
        "[class*='product'] img",
        "img[data-zoom-image]",
        "img[data-large_image]",
        "img",
    ]

    encontrados = []

    for sel in candidatos:
        try:
            el = soup.select_one(sel)
            if el:
                encontrados.append(sel)
        except Exception:
            continue

    return _escolher_primeiro_valido(encontrados)


def _detectar_links_produto(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        "a[href*='produto']",
        "a[href*='product']",
        "a[href*='/p/']",
        "a[class*='product']",
        "a[class*='produto']",
    ]
    encontrados = []

    for sel in candidatos:
        try:
            if soup.select_one(sel):
                encontrados.append(sel)
        except Exception:
            continue

    return _escolher_primeiro_valido(encontrados)


def _detectar_links_paginacao(soup: BeautifulSoup) -> list[str]:
    candidatos = [
        "a[rel='next']",
        "a[href*='page=']",
        "a[href*='pagina=']",
        "a[class*='next']",
        "a[class*='pagination']",
        "a[class*='page']",
        "a[class*='load-more']",
        "button[class*='load-more']",
    ]
    encontrados = []

    for sel in candidatos:
        try:
            if soup.select_one(sel):
                encontrados.append(sel)
        except Exception:
            continue

    return _escolher_primeiro_valido(encontrados)


def analisar_fornecedor_por_html(url: str, html: str) -> dict[str, Any]:
    dominio = extrair_dominio(url)
    soup = BeautifulSoup(html or "", "html.parser")
    tipo = _detectar_tipo_loja(html, soup)

    config = {
        "dominio": dominio,
        "tipo": tipo,
        "confianca": 0.75,
        "origem": "ia_adaptativa",
        "imagens_multiplas": True,
        "seletores": {
            "nome": _detectar_selectores_nome(soup),
            "preco": _detectar_selectores_preco(soup),
            "descricao": _detectar_selectores_descricao(soup),
            "imagem": _detectar_selectores_imagem(soup),
        },
        "links": {
            "produto": _detectar_links_produto(soup),
            "paginacao": _detectar_links_paginacao(soup),
        },
    }

    # aumenta confiança se achou bem os principais campos
    score = 0.0
    if config["seletores"]["nome"]:
        score += 0.1
    if config["seletores"]["preco"]:
        score += 0.1
    if config["seletores"]["imagem"]:
        score += 0.05
    if config["links"]["produto"]:
        score += 0.1

    config["confianca"] = round(min(0.95, config["confianca"] + score), 2)
    return config


def garantir_fornecedor_adaptativo(url: str, html: str) -> dict[str, Any]:
    dominio = extrair_dominio(url)
    if not dominio:
        return {}

    existente = carregar_fornecedor(dominio)
    if existente:
        return existente

    config = analisar_fornecedor_por_html(url, html)
    salvar_fornecedor(dominio, config, sobrescrever=False)
    return carregar_fornecedor(dominio) or config
