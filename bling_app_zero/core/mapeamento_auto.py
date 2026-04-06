from __future__ import annotations

import pandas as pd


def sugestao_automatica(df: pd.DataFrame, colunas_destino: list[str] | None = None) -> dict:
    """
    Gera sugestões automáticas de mapeamento entre colunas da origem e destino.

    Compatível com:
    - chamada antiga: sugestao_automatica(df)
    - chamada nova: sugestao_automatica(df, colunas_destino)

    Retorna:
        dict {coluna_destino: coluna_origem}
    """

    if df is None or df.empty:
        return {}

    colunas_origem = list(df.columns)

    # Se não tiver colunas destino → usa as mesmas da origem
    if not colunas_destino:
        return {col: col for col in colunas_origem}

    sugestoes = {}

    for destino in colunas_destino:
        destino_lower = destino.lower()

        melhor_match = None

        for origem in colunas_origem:
            origem_lower = origem.lower()

            # 🔥 regra simples mas eficiente
            if destino_lower == origem_lower:
                melhor_match = origem
                break

            if destino_lower in origem_lower:
                melhor_match = origem

        if melhor_match:
            sugestoes[destino] = melhor_match

    return sugestoes
