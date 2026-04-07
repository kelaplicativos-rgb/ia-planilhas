from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .fornecedores_adaptativos_storage import extrair_dominio, texto_limpo_fornecedor


# ==========================================================
# IA ADAPTATIVA (HEURÍSTICA)
# ==========================================================
def coletar_classes_fornecedor(el) -> str:
    try:
        classes = el.get("class", []) or []
        if isinstance(classes, str):
            return classes.strip()
        return " ".join(str(c).strip() for c in classes if str(c).strip())
    except Exception:
        return ""


def css_path_simples_fornecedor(el) -> str:
    try:
        nome = (el.name or "").strip()
        if not nome:
            return ""

        el_id = texto_limpo_fornecedor(el.get("id"))
        if el_id:
            return f"{nome}#{el_id}"

        classes = coletar_classes_fornecedor(el)
        if classes:
            primeira = classes.split()[0].strip()
            if primeira:
                return f"{nome}.{primeira}"

        return nome
    except Exception:
        return ""


def escolher_primeiro_valido_fornecedor(candidatos: list[str]) -> list[str]:
    vistos = set()
    saida = []

    for item in candidatos:
        item = texto_limpo_fornecedor(item)
        if not item:
            continue
        if item in vistos:
            continue
        vistos.add(item)
        saida.append(item)

    return saida[:8]


def detectar_tipo_loja_fornecedor(html: str, soup: BeautifulSoup) -> str:
    texto = (html or "").lower()

    if (
        "woocommerce" in texto
        or soup.select_one(".woocommerce")
        or soup.select_one(".product_title")
    ):
        return "woocommerce"

    if (
        "shopify" in texto
        or "cdn.shopify.com" in texto
        or soup.select_one("[class*='shopify']")
    ):
        return "shopify"

    if "vtex" in texto or "__vtex" in texto or soup.select_one("[class*='vtex']"):
        return "vtex"

    return "generico"


def detectar_selectores_nome_fornecedor(soup: BeautifulSoup) -> list[str]:
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
            if el and texto_limpo_fornecedor(el.get_text(" ", strip=True)):
                encontrados.append(sel)
        except Exception:
            continue

    for el in soup.find_all(["h1", "h2"]):
        texto = texto_limpo_fornecedor(el.get_text(" ", strip=True))
        if len(texto) >= 4:
            path = css_path_simples_fornecedor(el)
            if path:
                encontrados.append(path)

    return escolher_primeiro_valido_fornecedor(encontrados)


def detectar_selectores_preco_fornecedor(soup: BeautifulSoup) -> list[str]:
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
                val = texto_limpo_fornecedor(el.get("content"))
            else:
                val = texto_limpo_fornecedor(el.get_text(" ", strip=True))

            if val:
                encontrados.append(sel)
        except Exception:
            continue

    for el in soup.find_all(True):
        classes = coletar_classes_fornecedor(el).lower()
        if "price" in classes or "preco" in classes or "valor" in classes:
            texto = texto_limpo_fornecedor(el.get_text(" ", strip=True))
            if texto:
                path = css_path_simples_fornecedor(el)
                if path:
                    encontrados.append(path)

    return escolher_primeiro_valido_fornecedor(encontrados)


def detectar_selectores_descricao_fornecedor(soup: BeautifulSoup) -> list[str]:
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
                val = texto_limpo_fornecedor(el.get("content"))
            else:
                val = texto_limpo_fornecedor(el.get_text(" ", strip=True))

            if val:
                encontrados.append(sel)
        except Exception:
            continue

    return escolher_primeiro_valido_fornecedor(encontrados)


def detectar_selectores_imagem_fornecedor(soup: BeautifulSoup) -> list[str]:
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

    return escolher_primeiro_valido_fornecedor(encontrados)


def detectar_links_produto_fornecedor(soup: BeautifulSoup) -> list[str]:
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

    return escolher_primeiro_valido_fornecedor(encontrados)


def detectar_links_paginacao_fornecedor(soup: BeautifulSoup) -> list[str]:
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

    return escolher_primeiro_valido_fornecedor(encontrados)


def analisar_fornecedor_por_html(url: str, html: str) -> dict[str, Any]:
    dominio = extrair_dominio(url)
    soup = BeautifulSoup(html or "", "html.parser")
    tipo = detectar_tipo_loja_fornecedor(html, soup)

    config = {
        "dominio": dominio,
        "tipo": tipo,
        "confianca": 0.75,
        "origem": "ia_adaptativa",
        "imagens_multiplas": True,
        "principal": False,
        "seletores": {
            "nome": detectar_selectores_nome_fornecedor(soup),
            "preco": detectar_selectores_preco_fornecedor(soup),
            "descricao": detectar_selectores_descricao_fornecedor(soup),
            "imagem": detectar_selectores_imagem_fornecedor(soup),
        },
        "links": {
            "produto": detectar_links_produto_fornecedor(soup),
            "paginacao": detectar_links_paginacao_fornecedor(soup),
        },
    }

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
