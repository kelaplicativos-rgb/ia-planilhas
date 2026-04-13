from __future__ import annotations

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
)

from .site_crawler_shared import (
    fetch_inteligente,
    log_debug,
    mesmo_dominio,
    normalizar_link,
    parece_link_produto_flexivel,
)


def coletar_paginas_listagem(url_inicial: str, max_paginas: int) -> list[tuple[str, str]]:
    visitadas: set[str] = set()
    fila: list[str] = [url_inicial]
    paginas: list[tuple[str, str]] = []

    while fila and len(paginas) < max_paginas:
        url = fila.pop(0)
        if not url or url in visitadas:
            continue

        visitadas.add(url)

        payload = fetch_inteligente(url)
        html = str(payload.get("html") or "").strip()
        if not html:
            continue

        paginas.append((url, html))

        try:
            novos = extrair_links_paginacao_crawler(html, url) or []
            for n in novos:
                n_norm = normalizar_link(url, n)
                if not n_norm:
                    continue
                if not mesmo_dominio(url_inicial, n_norm):
                    continue
                if n_norm not in visitadas and n_norm not in fila:
                    fila.append(n_norm)
        except Exception as e:
            log_debug(f"[CRAWLER] erro paginação: {url} | {e}", "WARNING")

    return paginas


def extrair_links_agressivo(html: str, base_url: str) -> list[str]:
    links: list[str] = []

    try:
        links = extrair_links_produtos_crawler(html, base_url) or []
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair_links_produtos_crawler: {e}", "WARNING")
        links = []

    normalizados: list[str] = []
    vistos: set[str] = set()

    for item in links:
        url = normalizar_link(base_url, item)
        if not url or url in vistos:
            continue
        if not mesmo_dominio(base_url, url):
            continue
        vistos.add(url)
        normalizados.append(url)

    links = normalizados

    if len(links) < 3:
        soup = BeautifulSoup(html, "html.parser")
        candidatos: list[str] = []

        for a in soup.find_all("a"):
            href = a.get("href")
            url = normalizar_link(base_url, href)
            if not url:
                continue
            if not mesmo_dominio(base_url, url):
                continue

            texto_link = " ".join(a.get_text(" ", strip=True).split()).lower()
            low = url.lower()
            score = 0

            if any(x in low for x in ["/produto", "/product", "/prod/", "/item/", "/p/", "/sku/"]):
                score += 3

            if any(x in texto_link for x in ["comprar", "ver produto", "detalhes", "saiba mais"]):
                score += 2

            path = low.split("?", 1)[0]
            partes = [p for p in path.split("/") if p.strip()]
            if len(partes) >= 2:
                score += 1

            if parece_link_produto_flexivel(url):
                score += 2

            if score >= 2:
                candidatos.append(url)

        for item in candidatos:
            if item not in vistos:
                vistos.add(item)
                links.append(item)

    links_filtrados: list[str] = []
    vistos_finais: set[str] = set()

    for link in links:
        if not link:
            continue
        if link in vistos_finais:
            continue
        if not mesmo_dominio(base_url, link):
            continue
        if not parece_link_produto_flexivel(link):
            continue

        vistos_finais.add(link)
        links_filtrados.append(link)

    log_debug(f"[LINKS DETECTADOS] {len(links_filtrados)}", "INFO")
    return links_filtrados
