from __future__ import annotations

import json

from bs4 import BeautifulSoup


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
