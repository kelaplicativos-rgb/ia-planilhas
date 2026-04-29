# bling_app_zero/core/instant_scraper/ultra_detector.py

from bs4 import BeautifulSoup
from collections import defaultdict


def detectar_blocos_repetidos(html: str):
    soup = BeautifulSoup(html, "lxml")

    grupos = defaultdict(list)

    for el in soup.find_all(["div", "li", "article", "section"]):
        filhos = el.find_all(recursive=False)

        if len(filhos) < 2:
            continue

        tag_pattern = tuple(child.name for child in filhos[:5])

        grupos[tag_pattern].append(el)

    candidatos = []

    for pattern, elements in grupos.items():
        if len(elements) < 3:
            continue

        score = len(elements) * len(pattern)

        candidatos.append({
            "pattern": pattern,
            "elements": elements,
            "score": score
        })

    candidatos.sort(key=lambda x: x["score"], reverse=True)

    return candidatos[:5]
