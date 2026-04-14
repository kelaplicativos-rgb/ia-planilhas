from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# ==========================================================
# VERSION
# ==========================================================
HELPERS_VERSION = "V2_MODULAR_OK"

MAX_THREADS = 12
MAX_PAGINAS = 12
MAX_PRODUTOS = 1200

# ==========================================================
# URL / TEXTO
# ==========================================================
def normalizar_url_crawler(base_url: str, href: str | None) -> str:
    if not href:
        return ""

    href = str(href).strip()
    if not href:
        return ""

    url = urljoin(base_url, href)

    try:
        parsed = urlparse(url)
        url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        pass

    return url


def url_mesmo_dominio_crawler(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(str(url_base or "")).netloc.replace("www.", "").lower()
        d2 = urlparse(str(url or "")).netloc.replace("www.", "").lower()

        if not d1 or not d2:
            return False

        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def texto_limpo_crawler(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def numero_texto_crawler(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    texto = texto.replace("R$", "").replace("r$", "").strip()

    # tenta pegar preço completo primeiro (ex: 1.299,90)
    m = re.search(r"(\d{1,3}(?:[\.\,]\d{3})*(?:[\.\,]\d{2}))", texto)
    if m:
        return m.group(1)

    # fallback simples
    m2 = re.search(r"(\d+)", texto)
    return m2.group(1) if m2 else ""


# ==========================================================
# JSON-LD
# ==========================================================
def extrair_json_ld_crawler(soup: BeautifulSoup) -> list[dict]:
    dados: list[dict] = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            conteudo = script.string or script.text
            if not conteudo:
                continue

            json_data = json.loads(conteudo)

            if isinstance(json_data, list):
                dados.extend([x for x in json_data if isinstance(x, dict)])
            elif isinstance(json_data, dict):
                dados.append(json_data)
        except Exception:
            continue

    return dados


def buscar_produto_jsonld_crawler(jsonlds: list[dict]) -> dict:
    for item in jsonlds:
        if isinstance(item, dict) and "product" in str(item.get("@type", "")).lower():
            return item
    return {}


# ==========================================================
# META / TEXTO
# ==========================================================
def meta_content_crawler(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    return str(tag.get("content", "")).strip() if tag else ""


def primeiro_texto_crawler(soup: BeautifulSoup, seletores: list[str]) -> str:
    for sel in seletores:
        el = soup.select_one(sel)
        if el:
            txt = texto_limpo_crawler(el.get_text(" ", strip=True))
            if txt:
                return txt
    return ""


def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    imagens: list[str] = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        url = normalizar_url_crawler(base_url, src)
        if not url:
            continue

        if not any(x in url.lower() for x in ["logo", "icon", "placeholder", "thumb"]):
            if url not in imagens:
                imagens.append(url)

    return " | ".join(imagens[:5])


# ==========================================================
# ESTOQUE
# ==========================================================
def _texto_base_estoque_crawler(html: str, soup: BeautifulSoup) -> str:
    partes: list[str] = []

    try:
        partes.append(texto_limpo_crawler(html).lower())
    except Exception:
        pass

    try:
        if soup is not None:
            partes.append(texto_limpo_crawler(soup.get_text(" ", strip=True)).lower())
    except Exception:
        pass

    return " ".join([p for p in partes if p]).strip()


def _extrair_numeros_relevantes_estoque_crawler(texto: str) -> list[int]:
    if not texto:
        return []

    numeros: list[int] = []

    padroes = [
        r"(?:estoque|stock|dispon[ií]veis?|restam|restante|quantidade|qtd|qtde)\D{0,20}(\d{1,5})",
        r"(\d{1,5})\D{0,20}(?:unidades?|itens?|pe[çc]as?)\D{0,20}(?:em estoque|dispon[ií]veis?)",
        r"(?:somente|apenas|restam)\D{0,20}(\d{1,5})",
    ]

    for padrao in padroes:
        for match in re.finditer(padrao, texto, flags=re.IGNORECASE):
            try:
                valor = int(match.group(1))
                if 0 <= valor <= 99999:
                    numeros.append(valor)
            except Exception:
                continue

    return numeros


def _extrair_estoque_de_atributos_crawler(soup: BeautifulSoup) -> int | None:
    if soup is None:
        return None

    attrs_alvo = [
        "data-stock",
        "data-quantity",
        "data-qty",
        "data-qtd",
        "data-estoque",
        "data-product_stock",
        "data-available",
        "max",
    ]

    for tag in soup.find_all(True):
        for attr in attrs_alvo:
            try:
                valor = tag.get(attr)
            except Exception:
                valor = None

            if valor is None:
                continue

            texto = texto_limpo_crawler(valor)
            if not texto:
                continue

            if re.fullmatch(r"\d{1,5}", texto):
                try:
                    numero = int(texto)
                    if 0 <= numero <= 99999:
                        return numero
                except Exception:
                    continue

    return None


def _extrair_estoque_jsonld_crawler(soup: BeautifulSoup) -> int | None:
    try:
        jsonlds = extrair_json_ld_crawler(soup)
    except Exception:
        return None

    if not jsonlds:
        return None

    for item in jsonlds:
        if not isinstance(item, dict):
            continue

        bloco_ofertas = item.get("offers")
        ofertas = bloco_ofertas if isinstance(bloco_ofertas, list) else [bloco_ofertas]

        for oferta in ofertas:
            if not isinstance(oferta, dict):
                continue

            qtd = oferta.get("inventoryLevel")
            if isinstance(qtd, dict):
                qtd = qtd.get("value") or qtd.get("amount") or qtd.get("name")

            if qtd is not None:
                texto = texto_limpo_crawler(qtd)
                if re.fullmatch(r"\d{1,5}", texto):
                    try:
                        numero = int(texto)
                        if 0 <= numero <= 99999:
                            return numero
                    except Exception:
                        pass

            disponibilidade = str(
                oferta.get("availability") or oferta.get("availabilityStarts") or ""
            ).lower()

            if any(x in disponibilidade for x in ["outofstock", "outsold", "soldout"]):
                return 0

            if "instock" in disponibilidade:
                # disponível, mas sem quantidade confiável
                return None

    return None


def detectar_estoque_crawler(html: str, soup: BeautifulSoup, padrao: int) -> int:
    """
    Regra correta do projeto:
    - usa estoque real quando conseguir extrair
    - se detectar indisponibilidade, retorna 0
    - se não houver quantidade confiável, fallback é 0
    - nunca usar 10 fake por padrão
    """
    _ = padrao  # mantido por compatibilidade de assinatura

    texto = _texto_base_estoque_crawler(html, soup)

    sinais_sem_estoque = [
        "esgotado",
        "indisponível",
        "indisponivel",
        "out of stock",
        "sem estoque",
        "produto esgotado",
        "temporariamente indisponível",
        "temporariamente indisponivel",
        "zerado",
        "não disponível",
        "nao disponivel",
        "no stock",
        "sold out",
    ]

    if any(x in texto for x in sinais_sem_estoque):
        return 0

    # 1) tenta atributos HTML específicos
    estoque_attr = _extrair_estoque_de_atributos_crawler(soup)
    if estoque_attr is not None:
        return max(0, int(estoque_attr))

    # 2) tenta JSON-LD
    estoque_jsonld = _extrair_estoque_jsonld_crawler(soup)
    if estoque_jsonld is not None:
        return max(0, int(estoque_jsonld))

    # 3) tenta padrões textuais com quantidade explícita
    numeros = _extrair_numeros_relevantes_estoque_crawler(texto)
    if numeros:
        return max(0, int(numeros[0]))

    # 4) se só encontrou sinais de disponibilidade sem número real,
    # não inventa estoque
    sinais_disponivel_sem_qtd = [
        "comprar",
        "adicionar ao carrinho",
        "adicionar",
        "buy now",
        "em estoque",
        "disponível",
        "disponivel",
        "in stock",
    ]

    if any(x in texto for x in sinais_disponivel_sem_qtd):
        return 0

    # 5) fallback final obrigatório do projeto
    return 0


# ==========================================================
# DETECÇÃO DE PRODUTO
# ==========================================================
def link_parece_produto_crawler(url: str) -> bool:
    u = (url or "").lower()

    if any(
        x in u
        for x in [
            "javascript:",
            "mailto:",
            "#",
            "login",
            "conta",
            "carrinho",
            "checkout",
            "categoria",
            "category",
        ]
    ):
        return False

    sinais = [
        "/produto",
        "/product",
        "/p/",
        "/prod/",
        "/item/",
        "/sku/",
        "produto-",
        "product-",
    ]

    return any(s in u for s in sinais)


# ==========================================================
# LINKS PRODUTOS
# ==========================================================
def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        url = normalizar_url_crawler(base_url, href)

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        u = url.lower()

        # ignora lixo
        if any(
            x in u
            for x in [
                "login",
                "conta",
                "carrinho",
                "checkout",
                "categoria",
                "category",
                "blog",
                "javascript:",
                "#",
            ]
        ):
            continue

        # 1) mantém compatibilidade com padrão clássico
        if link_parece_produto_crawler(url):
            links.append(url)
            continue

        # 2) fallback heurístico para sites com slug customizado
        path = urlparse(u).path or ""
        partes = [p for p in path.split("/") if p.strip()]

        if (
            len(u) > 30
            and "-" in u
            and len(partes) >= 1
            and not u.endswith((".jpg", ".png", ".svg", ".webp", ".jpeg"))
        ):
            links.append(url)

    return list(dict.fromkeys(links))[:300]


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        url = normalizar_url_crawler(base_url, a.get("href"))

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(
            x in url.lower()
            for x in [
                "page=",
                "pagina",
                "/page/",
                "/pagina/",
                "?p=",
                "&p=",
                "pg=",
                "offset",
                "start",
            ]
        ):
            links.append(url)

    return list(dict.fromkeys(links))
