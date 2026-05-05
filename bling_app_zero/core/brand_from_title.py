from __future__ import annotations

"""Extração conservadora de marca usando apenas o título do produto.

Regra:
- Não buscar marca em descrição complementar, categoria, atributos ou texto solto.
- Usar somente o título/nome do produto.
- Só preencher quando a marca aparecer como token claro no título.
"""

import re
import unicodedata


KNOWN_BRANDS: dict[str, str] = {
    "LEHMOX": "Lehmox",
    "JBL": "JBL",
    "INTELBRAS": "Intelbras",
    "TOSHIBA": "Toshiba",
    "APPLE": "Apple",
    "SAMSUNG": "Samsung",
    "XIAOMI": "Xiaomi",
    "MULTILASER": "Multilaser",
    "EXBOM": "Exbom",
    "KNUP": "Knup",
    "SUMEXR": "Sumexr",
    "ELG": "ELG",
    "EJ": "EJ",
    "B MAX": "B-Max",
    "B-MAX": "B-Max",
    "H MASTON": "H'Maston",
    "HMASTON": "H'Maston",
    "H'MASTON": "H'Maston",
    "MOTOROLA": "Motorola",
    "LG": "LG",
    "SONY": "Sony",
    "PHILCO": "Philco",
    "MONDIAL": "Mondial",
    "BRITANIA": "Britânia",
    "BRITÂNIA": "Britânia",
    "POSITIVO": "Positivo",
    "MULTI": "Multi",
    "GOOGLE": "Google",
    "AMAZON": "Amazon",
    "AOC": "AOC",
    "DELL": "Dell",
    "HP": "HP",
    "LENOVO": "Lenovo",
    "ASUS": "Asus",
    "ACER": "Acer",
    "KINGSTON": "Kingston",
    "SANDISK": "SanDisk",
}


def _normalize_title(title: object) -> str:
    text = "" if title is None else str(title)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().strip()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def infer_brand_from_title(title: object) -> str:
    normalized = _normalize_title(title)
    if not normalized:
        return ""

    padded = f" {normalized} "

    # Ordena por tamanho para marcas compostas terem prioridade sobre tokens curtos.
    for token, brand in sorted(KNOWN_BRANDS.items(), key=lambda item: len(item[0]), reverse=True):
        token_norm = _normalize_title(token)
        if token_norm and f" {token_norm} " in padded:
            return brand

    return ""
