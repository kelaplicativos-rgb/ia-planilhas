# bling_app_zero/core/instant_scraper/ultra_detector.py

from __future__ import annotations

from collections import defaultdict
from typing import Any

from bs4 import BeautifulSoup


MAX_HTML_CHARS = 800_000
MAX_ELEMENTOS_ANALISADOS = 1_200
MAX_ELEMENTOS_POR_GRUPO = 80
MAX_CANDIDATOS = 8


def _txt(valor: Any) -> str:
    return str(valor or "").strip()


def _classe_resumida(el) -> str:
    classes = el.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()

    uteis = []
    for c in classes[:4]:
        c = _txt(c).lower()
        if c and len(c) <= 40:
            uteis.append(c)

    return ".".join(uteis)


def _tem_sinal_produto(el) -> bool:
    texto = el.get_text(" ", strip=True).lower()

    sinais = [
        "r$",
        "comprar",
        "produto",
        "preço",
        "preco",
        "sku",
        "cód",
        "cod",
        "ref",
        "adicionar",
    ]

    if any(s in texto for s in sinais):
        return True

    if el.find("img"):
        return True

    if el.find("a", href=True):
        return True

    return False


def detectar_blocos_repetidos(html: str):
    html = _txt(html)

    if not html:
        return []

    html = html[:MAX_HTML_CHARS]

    soup = BeautifulSoup(html, "lxml")
    grupos = defaultdict(list)

    elementos = soup.find_all(["div", "li", "article", "section"], limit=MAX_ELEMENTOS_ANALISADOS)

    for el in elementos:
        if not _tem_sinal_produto(el):
            continue

        filhos = el.find_all(recursive=False, limit=8)

        if len(filhos) < 2:
            continue

        tag_pattern = tuple(child.name for child in filhos[:5])
        classe = _classe_resumida(el)
        pattern = (el.name, classe, tag_pattern)

        if len(grupos[pattern]) < MAX_ELEMENTOS_POR_GRUPO:
            grupos[pattern].append(el)

    candidatos = []

    for pattern, elements in grupos.items():
        if len(elements) < 2:
            continue

        texto_total = " ".join(el.get_text(" ", strip=True).lower()[:500] for el in elements[:10])

        score = len(elements) * 10

        if "r$" in texto_total:
            score += 80

        if "comprar" in texto_total or "adicionar" in texto_total:
            score += 40

        imagens = sum(1 for el in elements[:20] if el.find("img"))
        links = sum(1 for el in elements[:20] if el.find("a", href=True))

        score += imagens * 5
        score += links * 4

        candidatos.append(
            {
                "pattern": pattern,
                "elements": elements,
                "score": score,
            }
        )

    candidatos.sort(key=lambda x: x["score"], reverse=True)

    return candidatos[:MAX_CANDIDATOS]
