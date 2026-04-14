from __future__ import annotations

import re

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers_jsonld import extrair_json_ld_crawler
from bling_app_zero.core.site_crawler_helpers_text import texto_limpo_crawler


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
    _ = padrao

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

    estoque_attr = _extrair_estoque_de_atributos_crawler(soup)
    if estoque_attr is not None:
        return max(0, int(estoque_attr))

    estoque_jsonld = _extrair_estoque_jsonld_crawler(soup)
    if estoque_jsonld is not None:
        return max(0, int(estoque_jsonld))

    numeros = _extrair_numeros_relevantes_estoque_crawler(texto)
    if numeros:
        return max(0, int(numeros[0]))

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

    return 0
