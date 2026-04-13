from __future__ import annotations

import re
from typing import Any


def normalizar_texto(txt: Any) -> str:
    try:
        txt = str(txt or "").lower().strip()
        txt = re.sub(r"\s+", " ", txt)
        txt = re.sub(r"[^\w\s]", "", txt)
        return txt
    except Exception:
        return ""


def similaridade_simples(a: str, b: str) -> float:
    try:
        a = normalizar_texto(a)
        b = normalizar_texto(b)

        if not a or not b:
            return 0.0

        if a == b:
            return 1.0

        if a in b or b in a:
            return 0.7

        palavras_a = set(a.split())
        palavras_b = set(b.split())

        inter = palavras_a.intersection(palavras_b)
        union = palavras_a.union(palavras_b)

        if not union:
            return 0.0

        return len(inter) / len(union)
    except Exception:
        return 0.0


def escolher_melhor_match(coluna, opcoes):
    melhor = None
    score_melhor = 0.0

    for opcao in opcoes:
        score = similaridade_simples(coluna, opcao)
        if score > score_melhor:
            score_melhor = score
            melhor = opcao

    return melhor, score_melhor
