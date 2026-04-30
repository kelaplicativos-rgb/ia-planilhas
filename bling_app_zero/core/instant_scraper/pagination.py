from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


@dataclass
class PaginationResult:
    urls: list[str] = field(default_factory=list)
    motivo: str = ""


PALAVRAS_PROXIMA = [
    "próxima",
    "proxima",
    "próximo",
    "proximo",
    "next",
    "seguinte",
    "mais",
    "ver mais",
    "mostrar mais",
    ">",
    "›",
    "»",
]

PARAMETROS_PAGINA = ["page", "pagina", "p", "pg"]


def _txt(valor) -> str:
    return str(valor or "").strip()


def _normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _mesmo_host(url_a: str, url_b: str) -> bool:
    try:
        return urlparse(url_a).netloc.replace("www.", "") == urlparse(url_b).netloc.replace("www.", "")
    except Exception:
        return False


def detectar_link_proxima_pagina(html: str, base_url: str) -> str:
    html = _txt(html)
    base_url = _normalizar_url(base_url)
    if not html or not base_url:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    rel_next = soup.find("link", attrs={"rel": lambda v: v and "next" in str(v).lower()})
    if rel_next and rel_next.get("href"):
        url = urljoin(base_url, rel_next.get("href"))
        if _mesmo_host(base_url, url):
            return url

    for a in soup.find_all("a", href=True):
        classes = a.get("class", [])
        classes_texto = " ".join(classes).lower() if isinstance(classes, list) else _txt(classes).lower()
        texto = " ".join([
            _txt(a.get_text(" ", strip=True)).lower(),
            _txt(a.get("aria-label", "")).lower(),
            _txt(a.get("title", "")).lower(),
            classes_texto,
        ])
        if any(palavra in texto for palavra in PALAVRAS_PROXIMA):
            url = urljoin(base_url, a.get("href"))
            if _mesmo_host(base_url, url) and url != base_url:
                return url

    return ""


def gerar_url_paginada_por_parametro(url: str, pagina: int) -> str:
    url = _normalizar_url(url)
    if not url or pagina <= 1:
        return url

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    for parametro in PARAMETROS_PAGINA:
        if parametro in query:
            query[parametro] = [str(pagina)]
            return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    query["page"] = [str(pagina)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def parece_mesma_pagina(html_a: str, html_b: str) -> bool:
    a = re.sub(r"\s+", " ", _txt(html_a))[:5000]
    b = re.sub(r"\s+", " ", _txt(html_b))[:5000]
    return bool(a and b and a == b)


def coletar_paginas_genericas(
    url_inicial: str,
    fetcher: Callable[[str], str],
    max_paginas: int = 8,
) -> PaginationResult:
    url_inicial = _normalizar_url(url_inicial)
    if not url_inicial:
        return PaginationResult([], "url_vazia")

    visitadas: list[str] = []
    vistos = set()
    url_atual = url_inicial
    html_anterior = ""

    for pagina in range(1, max(1, int(max_paginas)) + 1):
        if not url_atual or url_atual in vistos:
            return PaginationResult(visitadas, "url_repetida")

        html = fetcher(url_atual)
        if not html:
            motivo = "primeira_pagina_sem_html" if pagina == 1 else "pagina_sem_html"
            return PaginationResult(visitadas, motivo)

        if html_anterior and parece_mesma_pagina(html_anterior, html):
            return PaginationResult(visitadas, "html_repetido")

        visitadas.append(url_atual)
        vistos.add(url_atual)

        proxima = detectar_link_proxima_pagina(html, url_atual)
        if proxima and proxima not in vistos:
            html_anterior = html
            url_atual = proxima
            continue

        proxima_parametro = gerar_url_paginada_por_parametro(url_inicial, pagina + 1)
        if proxima_parametro and proxima_parametro not in vistos:
            html_anterior = html
            url_atual = proxima_parametro
            continue

        return PaginationResult(visitadas, "sem_proxima")

    return PaginationResult(visitadas, "limite_max_paginas")
