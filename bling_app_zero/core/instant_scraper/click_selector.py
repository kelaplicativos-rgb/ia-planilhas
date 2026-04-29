# bling_app_zero/core/instant_scraper/click_selector.py

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


def gerar_opcoes_click_scraper(html: str, base_url: str, limite: int = 5) -> List[Dict[str, Any]]:
    """
    Detecta blocos repetidos e gera opções para o usuário escolher,
    simulando o comportamento de seleção visual do Instant Data Scraper.
    """
    candidatos = detectar_blocos_repetidos(html) or []
    opcoes: List[Dict[str, Any]] = []

    for idx, candidato in enumerate(candidatos[:limite], start=1):
        elements = candidato.get("elements", [])
        produtos = extrair_lista(elements, base_url)

        df = pd.DataFrame(produtos or []).fillna("")

        opcoes.append(
            {
                "id": idx,
                "score": candidato.get("score", 0),
                "pattern": candidato.get("pattern", ""),
                "total_elementos": len(elements),
                "total_produtos": len(df),
                "dataframe": df,
            }
        )

    return opcoes


def extrair_por_opcao_click(
    html: str,
    base_url: str,
    opcao_id: int = 1,
) -> pd.DataFrame:
    """
    Extrai os produtos da opção escolhida pelo usuário.
    """
    opcoes = gerar_opcoes_click_scraper(html, base_url)

    for opcao in opcoes:
        if int(opcao.get("id", 0)) == int(opcao_id):
            df = opcao.get("dataframe")
            if isinstance(df, pd.DataFrame):
                return df.copy().fillna("")

    return pd.DataFrame()
