from __future__ import annotations

from .ia_mapper_utils import escolher_melhor_match


def sugerir_mapeamento(colunas_origem, colunas_destino):
    mapeamento = {}

    for col in colunas_destino:
        melhor, score = escolher_melhor_match(col, colunas_origem)

        if melhor and score >= 0.5:
            mapeamento[col] = melhor

    return mapeamento
